import dataclasses
import inspect
import typing
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from fastapi import HTTPException, Request
from pydantic.generics import GenericModel
from sqlalchemy.future.engine import Engine
from sqlalchemy.orm import exc as sa_exceptions
from sqlalchemy.orm import joinedload
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar


class TCreate(SQLModel):
    pass


class TUpdate(SQLModel):
    pass


class TIncludeParam(str):
    pass


TRead = TypeVar("TRead", bound=SQLModel)
TDb = TypeVar("TDb", bound=SQLModel)
TIncluded = TypeVar("TIncluded")
TypeVarType = Any


@dataclasses.dataclass
class Relationship:
    schema: Type[SQLModel]
    many: bool


class JAResource(GenericModel, Generic[TRead]):
    id: str
    type: str
    attributes: TRead


class JAResponseSingle(GenericModel, Generic[TRead, TIncluded]):
    data: JAResource[TRead]
    included: List[TIncluded]


class JAResponseList(GenericModel, Generic[TRead, TIncluded]):
    data: List[JAResource[TRead]]
    included: List[TIncluded]


class GetInclusions(Protocol):
    def __call__(self, request: Request, include: Optional[str] = None) -> list[str]:
        ...


class GetSelect(Protocol):
    def __call__(
        self, request: Request, inclusions: Optional[list[str]] = None
    ) -> SelectOfScalar:
        ...


class GetObject(Protocol):
    def __call__(
        self,
        id: int | str,
        request: Request,
        session: Session,
        inclusions: Optional[list[str]] = None,
    ) -> SQLModel:
        ...


class BuildResponse(Protocol):
    def __call__(
        self, rows: list[SQLModel], request: Request, inclusions: list[str], many: bool = False
    ) -> Union[JAResponseSingle, JAResponseList]:
        ...


class SQLResource(Protocol):
    name: str
    engine: Engine

    relationships: dict[str, Relationship]

    Db: Type[SQLModel]
    Read: Type[SQLModel]

    Create: Optional[Type[SQLModel]]
    Update: Optional[Type[SQLModel]]

    create: Optional[Callable]
    list: Optional[Callable]
    update: Optional[Callable]
    delete: Optional[Callable]
    retrieve: Optional[Callable]

    RetrieveResponseModel: Type[SQLModel] | Type[GenericModel]
    ListResponseModel: Type[SQLModel] | Type[GenericModel]

    get_select: GetSelect
    get_object: GetObject
    get_inclusions: GetInclusions
    build_response: BuildResponse


def get_related_schema(annotation: Any):
    args = typing.get_args(annotation)
    if args:
        generic_arg = args[0]
        if issubclass(generic_arg, SQLModel):
            # Generic assumes first arg is the model
            return generic_arg

        raise ValueError("Unsupported generic relationship type. Must be a single arg.")

    if issubclass(annotation, SQLModel):
        return annotation

    raise ValueError(f"Unsupported relationship type {annotation}")


class BaseSQLResource(SQLResource):
    def __init__(self, *args, **kwargs):
        # # Build the relationships for the Db model
        annotations = typing.get_type_hints(self.Db)
        relationship_fields = self.Db.__sqlmodel_relationships__.keys()

        self.relationships = {}

        for field in relationship_fields:
            annotated_type = annotations[field]
            related_schema = get_related_schema(annotated_type)
            many = typing.get_origin(annotated_type) == list

            self.relationships[field] = Relationship(
                schema=related_schema,
                many=many,
            )

        # Build response models
        Included = tuple(JAResource[r.schema] for r in self.relationships.values())
        self.RetrieveResponseModel = JAResponseSingle[self.Read, Union[Included]]
        self.ListResponseModel = JAResponseList[self.Read, Union[Included]]

        # Params to replace
        include_param = {TIncludeParam: Literal[tuple(relationship_fields)]}
        methods = {
            "create": {TCreate: self.Create, **include_param},
            "update": {TUpdate: self.Update, **include_param},
            "retrieve": include_param,
            "list": include_param,
        }

        for method_name, replacements in methods.items():
            method_instance = getattr(self, method_name, None)

            if not method_instance:
                continue

            original_signature = inspect.signature(method_instance)
            updated_params = [
                inspect.Parameter(
                    name=param.name,
                    kind=param.kind,
                    default=param.default,
                    annotation=replacements.get(param.annotation, param.annotation),
                )
                for param in original_signature.parameters.values()
            ]
            updated_signature = inspect.Signature(updated_params)

            # Required to avoid closing over method_name
            def factory(_method_name):
                def wrapper(*args, **kwargs):
                    class_method = getattr(self.__class__, _method_name)
                    return class_method(self, *args, **kwargs)

                return wrapper

            setattr(self, method_name, factory(method_name))
            getattr(self, method_name).__signature__ = updated_signature

        return super().__init__(*args, **kwargs)

    def get_inclusions(self, request: Request, include: str = None):
        # TODO: Support nested
        return include.split(",") if include else []

    def get_select(self, request: Request, inclusions: Optional[list[str]] = None):
        options = []
        inclusions = inclusions or []

        # Build the query options based on the include
        for inclusion in inclusions:
            options.append(joinedload(getattr(self.Db, inclusion)))

        return select(self.Db).options(*options)

    def get_object(
        self,
        request: Request,
        session: Session,
        id: int | str,
        inclusions: Optional[list[str]] = None,
    ):
        select = self.get_select(request=request, inclusions=inclusions)

        try:
            return session.exec(select.where(self.Db.id == id)).unique().one()
        except sa_exceptions.NoResultFound:
            raise HTTPException(status_code=404, detail=f"{self.name} not found")

    # Feels like this is the actual thing that handles JSON-API.
    # Additionally, filters/sorting could be applied by override the `list` to provide extra
    # params.
    # But it would also requirea a different router to because the response models would be different
    # I suppose that could be something built by the resource
    def build_response(
        self, rows: list[SQLModel], request: Request, inclusions: list[str], many: bool = False,
    ):
        included_resources = {}

        for row in rows:
            for inclusion in inclusions:
                included_objs = getattr(row, inclusion)
                if not included_objs:
                    continue

                included_objs = (
                    [included_objs]
                    if not isinstance(included_objs, list)
                    else included_objs
                )

                for included_obj in included_objs:
                    schema = self.relationships[inclusion].schema
                    included_resources[included_obj.id] = JAResource(
                        id=included_obj.id,
                        type=inclusion,
                        attributes=schema.from_orm(included_obj),
                    )

        data = [JAResource(id=row.id, attributes=row, type=self.name) for row in rows]
        data = data if many else data[0]
        ResponseSchema = JAResponseList if many else JAResponseSingle
        print(data)

        return ResponseSchema(
            data=data,
            included=list(included_resources.values()),
        )


class CreateResourceMixin:
    def create(
        self: SQLResource,
        request: Request,
        model: TCreate,
        include: TIncludeParam = None,
    ):
        with Session(self.engine) as session:
            row = self.Db.from_orm(model)
            session.add(row)
            session.commit()

            inclusions = self.get_inclusions(request=request, include=include)
            row = self.get_object(
                id=row.id, session=session, request=request, inclusions=inclusions
            )

            return self.build_response(
                rows=[row],
                request=request,
                inclusions=inclusions,
            )


class UpdateResourceMixin:
    def update(
        self: SQLResource,
        *,
        id: int,
        model: TUpdate,
        request: Request,
        include: TIncludeParam = None,
    ):
        with Session(self.engine) as session:
            inclusions = self.get_inclusions(request=request, include=include)
            row = self.get_object(
                id=id, session=session, request=request, inclusions=inclusions
            )

            data = model.dict(exclude_unset=True)
            for key, value in data.items():
                setattr(row, key, value)

            session.add(row)
            session.commit()
            session.refresh(row)

            return self.build_response(
                rows=[row],
                request=request,
                inclusions=inclusions,
            )


class ListResourceMixin:
    def list(self: SQLResource, request: Request, include: TIncludeParam = None):
        with Session(self.engine) as session:
            inclusions = self.get_inclusions(request=request, include=include)
            select = self.get_select(request=request, inclusions=inclusions)

            rows = session.exec(select).unique().all()

            return self.build_response(
                rows=rows,
                request=request,
                inclusions=inclusions,
                many=True,
            )


class RetrieveResourceMixin:
    def retrieve(
        self: SQLResource, *, id: int, include: TIncludeParam = None, request: Request
    ):
        with Session(self.engine) as session:
            inclusions = self.get_inclusions(request=request, include=include)
            row = self.get_object(
                id=id, session=session, request=request, inclusions=inclusions
            )

            return self.build_response(
                rows=[row],
                request=request,
                inclusions=inclusions,
            )


class DeleteResourceMixin:
    def delete(self: SQLResource, *, id: int, request: Request):
        with Session(self.engine) as session:
            row = self.get_object(id=id, session=session, request=request)

            session.delete(row)
            session.commit()

            return {"ok": True}


class ListCreateResource(CreateResourceMixin, ListResourceMixin, BaseSQLResource):
    pass


class ListCreateUpdateResource(
    ListResourceMixin,
    CreateResourceMixin,
    UpdateResourceMixin,
    BaseSQLResource,
):
    pass


class SQLModelResource(
    RetrieveResourceMixin,
    ListResourceMixin,
    CreateResourceMixin,
    UpdateResourceMixin,
    DeleteResourceMixin,
    BaseSQLResource,
):
    pass
