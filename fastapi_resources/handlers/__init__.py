import dataclasses
import types as builtin_types

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import MANYTOONE


def _emit_event(obj, event):
    """Append a domain event to obj.domain_events, initializing the list if needed."""
    if not hasattr(obj, "domain_events"):
        obj.domain_events = []
    obj.domain_events.append(event)


def build_handlers(Db, commands, uow):
    """Generate default CRUD handler functions for a SQLAlchemy model.

    Returns a namespace with .create, .update, .delete handler functions.
    Each handler uses uow.repo_for(Db) to access the correct repository.
    """
    pk_name = commands._pk_name
    user_assigned_pk = commands._user_assigned_pk
    db_init_fields = commands._db_init_fields

    # Map command FK field → (relationship_attr, related_class) for MANYTOONE
    # e.g. "galaxy_id" → ("galaxy", Galaxy)
    # Map command _ids field → (relationship_attr, related_class) for to-many
    # e.g. "planet_ids" → ("planets", Planet)
    inspected = sa_inspect(Db)
    rel_id_map = {}   # FK field name → (rel_attr, RelatedClass)
    rel_ids_map = {}  # _ids field name → (rel_attr, RelatedClass)
    for rel in inspected.relationships:
        if rel.direction == MANYTOONE:
            rel_id_map[f"{rel.key}_id"] = (rel.key, rel.mapper.class_)
        else:
            singular = rel.key[:-1] if rel.key.endswith("s") else rel.key
            rel_ids_map[f"{singular}_ids"] = (rel.key, rel.mapper.class_)

    def _split_kwargs(cmd):
        """Split command fields into scalar init_kwargs, to-one rel_kwargs, and to-many rel_ids_kwargs.

        Returns (init_kwargs, rel_kwargs, rel_ids_kwargs) where:
        - init_kwargs: scalars passed to Db.__init__
        - rel_kwargs: {(rel_attr, RelatedClass): related_id} — to-one relationships
        - rel_ids_kwargs: {(rel_attr, RelatedClass): [ids]} — to-many relationships
        """
        init_kwargs = {}
        rel_kwargs = {}
        rel_ids_kwargs = {}
        for f in dataclasses.fields(cmd):
            if f.name == pk_name and not user_assigned_pk:
                continue
            val = getattr(cmd, f.name)
            if f.name in rel_ids_map:
                if val is not None:
                    rel_ids_kwargs[rel_ids_map[f.name]] = val
            elif f.name in rel_id_map:
                if val is not None:
                    rel_kwargs[rel_id_map[f.name]] = val
            elif f.name in db_init_fields or f.name == pk_name:
                if val is not None:
                    init_kwargs[f.name] = val
        return init_kwargs, rel_kwargs, rel_ids_kwargs

    def create(cmd, uow=uow):
        with uow:
            init_kwargs, rel_kwargs, rel_ids_kwargs = _split_kwargs(cmd)
            obj = Db(**init_kwargs)
            uow.repo_for(Db).add(obj)  # session.add + flush → assigns DB-generated PKs
            for (rel_attr, related_cls), related_id in rel_kwargs.items():
                # Setting FK columns directly is overridden by the relationship during flush;
                # load the related object and set the relationship attribute instead.
                related_obj = uow.repo_for(related_cls).get(related_id)
                setattr(obj, rel_attr, related_obj)
            for (rel_attr, related_cls), ids in rel_ids_kwargs.items():
                related_objs = [uow.repo_for(related_cls).get(rid) for rid in ids]
                setattr(obj, rel_attr, related_objs)
            pk_val = getattr(obj, pk_name)
            _emit_event(obj, commands.Created(**{pk_name: pk_val}))
            uow.commit()
            return pk_val

    def update(cmd, uow=uow):
        with uow:
            repo = uow.repo_for(Db)
            obj = repo.get(getattr(cmd, pk_name), method="update")
            for f in dataclasses.fields(cmd):
                if f.name == pk_name:
                    continue
                val = getattr(cmd, f.name)
                if f.name in rel_ids_map:
                    if val is not None:
                        rel_attr, related_cls = rel_ids_map[f.name]
                        related_objs = [uow.repo_for(related_cls).get(rid) for rid in val]
                        setattr(obj, rel_attr, related_objs)
                elif f.name in rel_id_map:
                    if val is not None:
                        rel_attr, related_cls = rel_id_map[f.name]
                        related_obj = uow.repo_for(related_cls).get(val)
                        setattr(obj, rel_attr, related_obj)
                else:
                    if val is not None:
                        setattr(obj, f.name, val)
            _emit_event(obj, commands.Updated(**{pk_name: getattr(obj, pk_name)}))
            uow.commit()
            return getattr(obj, pk_name)

    def delete(cmd, uow=uow):
        with uow:
            repo = uow.repo_for(Db)
            obj = repo.get(getattr(cmd, pk_name), method="delete")
            pk_val = getattr(obj, pk_name)
            _emit_event(obj, commands.Deleted(**{pk_name: pk_val}))
            repo.remove(obj)
            uow.commit()

    return builtin_types.SimpleNamespace(create=create, update=update, delete=delete)
