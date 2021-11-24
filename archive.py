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
