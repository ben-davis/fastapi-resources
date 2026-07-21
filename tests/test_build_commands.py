import dataclasses

import pytest

from fastapi_resources.domain import Command, Event, build_commands
from tests.resources.sqlalchemy_models import (
    Galaxy,
    GalaxyCreate,
    GalaxyUpdate,
    Moon,
    MoonCreate,
    Star,
    StarCreate,
    StarUpdate,
)


class TestBuildCommandsFields:
    def test_create_command_has_scalar_fields(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        field_names = {f.name for f in dataclasses.fields(cmds.Create)}
        assert "name" in field_names
        # autoincrement PK is not user-assigned, so no id field
        assert "id" not in field_names

    def test_create_command_has_relationship_fields(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        field_names = {f.name for f in dataclasses.fields(cmds.Create)}
        # galaxy is MANYTOONE → galaxy_id
        assert "galaxy_id" in field_names
        # planets is ONETOMANY → planet_ids
        assert "planet_ids" in field_names

    def test_update_command_id_always_required(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        field_names = [f.name for f in dataclasses.fields(cmds.Update)]
        assert field_names[0] == "id"

    def test_update_command_scalar_fields_optional(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        fields = {f.name: f for f in dataclasses.fields(cmds.Update)}
        assert "name" in fields
        # Should have a default (optional)
        assert fields["name"].default is None or fields["name"].default_factory is not None  # type: ignore[misc]

    def test_delete_command_only_has_pk(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        field_names = [f.name for f in dataclasses.fields(cmds.Delete)]
        assert field_names == ["id"]

    def test_events_carry_only_pk(self):
        cmds = build_commands(Galaxy, Create=GalaxyCreate, Update=GalaxyUpdate)
        for event_cls in (cmds.Created, cmds.Updated, cmds.Deleted):
            field_names = [f.name for f in dataclasses.fields(event_cls)]
            assert field_names == ["id"]


class TestBuildCommandsBaseClasses:
    def test_commands_are_command_subclasses(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        assert issubclass(cmds.Create, Command)
        assert issubclass(cmds.Update, Command)
        assert issubclass(cmds.Delete, Command)

    def test_events_are_event_subclasses(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        assert issubclass(cmds.Created, Event)
        assert issubclass(cmds.Updated, Event)
        assert issubclass(cmds.Deleted, Event)

    def test_commands_are_frozen_dataclasses(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        cmd = cmds.Create(name="Sirius")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            cmd.name = "Vega"  # type: ignore[misc]


class TestBuildCommandsPkDetection:
    def test_autoincrement_pk_excluded_from_create(self):
        # Galaxy has id: Mapped[int] = mapped_column(primary_key=True, init=False)
        cmds = build_commands(Galaxy, Create=GalaxyCreate, Update=GalaxyUpdate)
        field_names = {f.name for f in dataclasses.fields(cmds.Create)}
        assert "id" not in field_names
        assert cmds._user_assigned_pk is False

    def test_user_pk_metadata(self):
        cmds = build_commands(Star, Create=StarCreate, Update=StarUpdate)
        assert cmds._pk_name == "id"
        assert cmds._pk_type == int

    def test_init_false_fk_excluded_from_db_init_fields(self):
        # Moon.planet_id is init=False, so it won't be in db_init_fields
        cmds = build_commands(Moon, Create=MoonCreate)
        assert "planet_id" not in cmds._db_init_fields
        assert "name" in cmds._db_init_fields
