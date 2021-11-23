from fastapi import FastAPI, HTTPException, Depends, APIRouter
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from sqlmodel import SQLModel, Field, create_engine, Session, select
import dataclasses

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

app = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


class HeroBase(SQLModel):
    name: str
    secret_name: str
    age: Optional[int] = None


class Hero(HeroBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class HeroCreate(HeroBase):
    pass


class HeroRead(HeroBase):
    id: int


class HeroUpdate(SQLModel):
    name: Optional[str] = None
    secret_name: Optional[str] = None
    age: Optional[int] = None


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


# @dataclasses.dataclass
# class Resource:
#     name: str
#     Db: Type

#     Read: Type = None
#     Create: Optional[Type] = None
#     Update: Optional[Type] = None

#     retrieve: Optional[Callable] = None
#     list: Optional[Callable] = None
#     create: Optional[Callable] = None
#     update: Optional[Callable] = None
#     delete: Optional[Callable] = None


# def build_resource(*funcs: Callable, **kwargs):
#     resource = Resource(**kwargs)

#     for func in funcs:
#         resource = func(resource=resource, **kwargs)

#     return resource


# def with_sqlmodel_create(*, resource: Resource, Db: Type, Create: Type, **kwargs):
#     def create(*, session: Session = Depends(get_session), model: Create):
#         row = Db.from_orm(model)
#         session.add(row)
#         session.commit()
#         session.refresh(row)
#         return row

#     resource.create = create

#     return resource


# def with_sqlmodel_retrieve(*, resource: Resource, Db: Type, name: str, **kwargs):
#     def retrieve(*, session: Session = Depends(get_session), id: int):
#         row = session.get(Db, id)
#         if not row:
#             raise HTTPException(status_code=404, detail=f"{name.title()} not found")

#         return row

#     resource.retrieve = retrieve

#     return resource


# def with_sqlmodel_list(*, resource: Resource, Db: Type, **kwargs):
#     def list(session: Session = Depends(get_session)):
#         rows = session.exec(select(Db)).all()
#         return rows

#     resource.list = list

#     return resource


# def with_sqlmodel_update(
#     *, resource: Resource, Db: Type, Update: Type, name: str, **kwargs
# ):
#     def update(*, session: Session = Depends(get_session), id: int, model: Update):
#         row = session.get(Db, id)

#         if not row:
#             raise HTTPException(status_code=404, detail=f"{name} not found")

#         data = model.dict(exclude_unset=True)
#         for key, value in data.items():
#             setattr(row, key, value)

#         session.add(row)
#         session.commit()
#         session.refresh(row)

#         return row

#     resource.update = update

#     return resource


# def with_sqlmodel_destroy(*, resource: Resource, Db: Type, name: str, **kwargs):
#     def delete(*, session: Session = Depends(get_session), id: int):
#         row = session.get(Db, id)
#         if not row:
#             raise HTTPException(status_code=404, detail=f"{name} not found")

#         session.delete(row)
#         session.commit()

#         return {"ok": True}

#     resource.delete = delete

#     return resource


# def sqlmodel_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
#     Create: Type,
#     Update: Type,
# ):
#     return build_resource(
#         with_sqlmodel_retrieve,
#         with_sqlmodel_list,
#         with_sqlmodel_create,
#         with_sqlmodel_update,
#         with_sqlmodel_destroy,
#         name=name,
#         Db=Db,
#         Read=Read,
#         Create=Create,
#         Update=Update,
#     )


# def sqlmodel_create_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
#     Create: Type,
# ):
#     return build_resource(
#         with_sqlmodel_create,
#         name=name,
#         Db=Db,
#         Read=Read,
#         Create=Create,
#     )


# def sqlmodel_list_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
# ):
#     return build_resource(
#         with_sqlmodel_list,
#         name=name,
#         Db=Db,
#         Read=Read,
#     )


# def sqlmodel_retrieve_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
# ):
#     return build_resource(
#         with_sqlmodel_retrieve,
#         name=name,
#         Db=Db,
#         Read=Read,
#     )


# def sqlmodel_read_only_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
# ):
#     return build_resource(
#         with_sqlmodel_retrieve,
#         with_sqlmodel_list,
#         name=name,
#         Db=Db,
#         Read=Read,
#     )


# def sqlmodel_update_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
#     Update: Type,
# ):
#     return build_resource(
#         with_sqlmodel_update,
#         name=name,
#         Db=Db,
#         Read=Read,
#         Update=Update,
#     )


# def sqlmodel_destroy_resource(
#     name: str,
#     Db: Type,
# ):
#     return build_resource(
#         with_sqlmodel_destroy,
#         name=name,
#         Db=Db,
#     )


# def sqlmodel_list_create_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
#     Create: Type,
# ):
#     return build_resource(
#         with_sqlmodel_list,
#         with_sqlmodel_create,
#         name=name,
#         Db=Db,
#         Read=Read,
#         Create=Create,
#     )


# def sqlmodel_retrieve_update_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
#     Update: Type,
# ):
#     return build_resource(
#         with_sqlmodel_retrieve,
#         with_sqlmodel_update,
#         name=name,
#         Db=Db,
#         Read=Read,
#         Update=Update,
#     )


# def sqlmodel_retrieve_destroy_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
# ):
#     return build_resource(
#         with_sqlmodel_retrieve,
#         with_sqlmodel_destroy,
#         name=name,
#         Db=Db,
#         Read=Read,
#     )


# def sqlmodel_retrieve_update_destroy_resource(
#     name: str,
#     Db: Type,
#     Read: Type,
#     Update: Type,
# ):
#     return build_resource(
#         with_sqlmodel_retrieve,
#         with_sqlmodel_update,
#         with_sqlmodel_destroy,
#         name=name,
#         Db=Db,
#         Read=Read,
#         Update=Update,
#     )


TCreate = TypeVar("TCreate", bound=SQLModel)
TUpdate = TypeVar("TUpdate", bound=SQLModel)
TypeVarType = Any


class SQLResource(Protocol):
    name: str

    Db: Type[SQLModel]
    Read: Type[SQLModel]
    # Create: Type[SQLModel]

    create: Optional[Callable]
    list: Optional[Callable]
    update: Optional[Callable]
    delete: Optional[Callable]
    retrieve: Optional[Callable]


class BaseSQLResource:
    create: Optional[Callable] = None
    list: Optional[Callable] = None
    update: Optional[Callable] = None
    delete: Optional[Callable] = None
    retrieve: Optional[Callable] = None

    if TYPE_CHECKING:
        # Putting this in a TYPE_CHECKING block allows us to replace `if Generic not in cls.__bases__` with
        # `not hasattr(cls, "__parameters__")`. This means we don't need to force non-concrete subclasses of
        # `GenericModel` to also inherit from `Generic`, which would require changes to the use of `create_model` below.
        __parameters__: ClassVar[Tuple[TypeVarType, ...]]

    # def __new__(cls, *args, **kwargs):
    #     breakpoint()
    #     super().__new__(cls, *args, **kwargs)
    def __class_getitem__(cls, params):
        methods = ["create", "list", "update", "delete", "retrieve"]

        if not isinstance(params, tuple):
            params = (params,)

        typevars_map: Dict[TypeVarType, Type[Any]] = dict(
            zip(cls.__parameters__, params)
        )

        for method_name in methods:
            method = getattr(cls, method_name, None)

            if not method:
                continue

            for attr, t in method.__annotations__.items():
                if t in typevars_map:
                    print("repalcing", attr, typevars_map[t])
                    method.__annotations__[attr] = typevars_map[t]

        return cls

    # def __init__(self, name: str, Db: Type, Read: Type):
    #     self.name = name
    #     self.Db = Db
    #     self.Read = Read


class CreateResourceMixin(BaseSQLResource, Generic[TCreate]):
    def create(self: SQLResource, *, session: Session = Depends(get_session), model: TCreate):
        row = self.Db.from_orm(model)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


class UpdateResourceMixin(BaseSQLResource, Generic[TUpdate]):
    def update(
        self: SQLResource,
        *,
        session: Session = Depends(get_session),
        id: int,
        model: TUpdate,
    ):
        row = session.get(self.Db, id)

        if not row:
            raise HTTPException(status_code=404, detail=f"{self.name} not found")

        data = model.dict(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        session.add(row)
        session.commit()
        session.refresh(row)

        return row


class ListResourceMixin:
    def list(self: SQLResource, session: Session = Depends(get_session)):
        rows = session.exec(select(self.Db)).all()
        return rows


class RetrieveResourceMixin:
    def retrieve(self: SQLResource, *, session: Session = Depends(get_session), id: int):
        row = session.get(self.Db, id)
        if not row:
            raise HTTPException(status_code=404, detail=f"{self.name.title()} not found")

        return row


class DeleteResourceMixin:
    def delete(self: SQLResource, *, session: Session = Depends(get_session), id: int):
        row = session.get(self.Db, id)
        if not row:
            raise HTTPException(status_code=404, detail=f"{self.name} not found")

        session.delete(row)
        session.commit()

        return {"ok": True}



class ListCreateResource(CreateResourceMixin[TCreate], ListResourceMixin, BaseSQLResource):
    pass


class ListCreateUpdateResource(
    ListResourceMixin,
    CreateResourceMixin[TCreate],
    UpdateResourceMixin[TUpdate],
    BaseSQLResource,
    Generic[TCreate, TUpdate],
):
    pass


class FullResource(
    RetrieveResourceMixin,
    ListResourceMixin,
    CreateResourceMixin[TCreate],
    UpdateResourceMixin[TUpdate],
    DeleteResourceMixin,
    BaseSQLResource,
    Generic[TCreate, TUpdate],
):
    pass


class ResourceRouter(APIRouter):
    def __init__(
        self,
        *,
        resource: SQLResource,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        if resource.retrieve:
            self.get(
                f"/{{id}}", response_model=resource.Read, summary=f"Get {resource.name}"
            )(resource.retrieve)

        if resource.list:
            Read = resource.Read
            self.get(
                f"/", response_model=List[Read], summary=f"Get {resource.name} list"
            )(resource.list)

        if resource.create:
            self.post(
                f"/", response_model=resource.Read, summary=f"Create {resource.name}"
            )(resource.create)

        if resource.update:
            self.patch(
                f"/{{id}}",
                response_model=resource.Read,
                summary=f"Update {resource.name}",
            )(resource.update)

        if resource.delete:
            self.delete(f"/{{id}}", summary=f"Delete {resource.name}")(resource.delete)


class HeroResource(FullResource[HeroCreate, HeroUpdate]):
    name = "hero"
    Db = Hero
    Read = HeroRead

    def list(self: SQLResource, session: Session = Depends(get_session)):
        print("LISTING")
        return super().list(session=session)

resource = HeroResource()

hero = ResourceRouter(prefix="/heroes", resource=resource)
# yolo = ResourceRouter(name="yolo", plural_name="yoloes", Db=Hero, Read=HeroRead)

app.include_router(hero)
# app.include_router(yolo)


"""
TODO:
- Relationships and automatically supported and documented `includes` with efficient prefetches.
- Post create & update hooks.
- An equivalent of get_queryset so users can do row-level permissions.
- How to support actions?
"""
