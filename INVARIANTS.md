# fastapi-resources Architecture Invariants

These are the rules of this codebase. They describe what this library is, what it is not, and how every part of it behaves.

---

## What This Library Is

fastapi-resources is a framework for structuring a system around cosmicpython principles. It provides four things that work together:

- **Repository factory** — generates data access classes from ORM models
- **Command + handler factory** — generates commands and default handlers for CRUD operations
- **Message bus** — routes commands to handlers and events to event handlers
- **JSON:API HTTP layer** — serializes domain objects into JSON:API responses and wires up FastAPI routes

The HTTP layer is one output of the framework. Commands, handlers, and repositories are equally first-class — they exist independently of HTTP and can be used from anywhere in the system.

---

## What a Resource Is

A resource does exactly three things:

1. **Parse** — extract typed attributes and relationships from the HTTP request
2. **Dispatch or query** — for writes, send a Command to the message bus; for reads, call the repository
3. **Serialize** — convert the result into a JSON:API response

A resource contains no business logic, no transaction management, no domain decisions, and no SQLAlchemy.

---

## The Repository

Every resource has a repository. The repository is the only thing in the resource that touches the database — and the resource only ever calls it, never looks inside it.

The repository has full read and write capability:

- `add(obj)` — persist a new aggregate
- `get(id, **filters)` — fetch a single aggregate by id, with optional auth filters
- `list(inclusions, **filters)` — fetch a collection, with filtering, pagination, and eager loading

All SQLAlchemy lives in the repository: `select()`, `joinedload()`, `where()` clauses, session access. None of it appears in the resource.

`get_where()` is a method on the repository, not the resource. It returns SQLAlchemy filter expressions and is the customisation point for row-level access control. The repository calls it internally when building queries.

The resource declares its repository via a class variable:

```python
class StarResource(SQLAlchemyResource[Star]):
    Repo = SqlAlchemyStarRepository
    Read = StarRead
    ...
```

The base class instantiates the repository from the injected session and assigns it to `self.repo`. The resource never sees the session.

```python
# BaseSQLAlchemyResource.__init__:
def __init__(self, session, ...):
    self.repo = self.Repo(session)
    # self.session does not exist
```

---

## The Message Bus

The library provides `MessageBus`. It routes commands to a single handler and events to zero or more handlers.

```python
from fastapi_resources import MessageBus

bus = MessageBus()
```

Rules:
- **Command handlers** fail loudly — exceptions propagate to the caller
- **Event handlers** fail silently — exceptions are logged, remaining handlers still run
- After each handler, new domain events are collected from the UoW and queued for dispatch
- The message bus returns the command handler's return value; event dispatch returns nothing

All handler registration is explicit — no factory auto-registers anything. The application calls `bus.register(CommandType, handler)` or `bus.register_resource(commands, handlers)` to wire everything together.

The router receives the bus at startup and makes it available to resources via `self.messagebus_handle`. The resource calls `self.messagebus_handle(cmd)` — it has no direct reference to the bus itself.

---

## Writes — Command Dispatch

Write methods construct a Command and dispatch it via `self.messagebus_handle`. They do not touch the repository for writes.

Commands carry a pre-generated ID so the resource can re-fetch the result after the handler commits:

```python
def create(self, attributes, relationships) -> Star:
    star_id = generate_id()
    self.messagebus_handle(CreateStar(
        id=star_id,
        name=attributes["name"],
        planet_ids=relationships.get("planets", []),
    ))
    return self.repo.get(star_id)
```

Rules:
- Resources never call `session.add()`, `session.commit()`, or `uow.commit()`
- Resources never open a `with uow:` block
- Resources re-fetch the result via `self.repo.get(id)` after dispatch — they do not use the object returned by the handler directly, as it belongs to the handler's session
- If a write method contains a domain `if`-branch, it belongs in a handler instead

---

## The Unit of Work

The UoW lives in the **handler layer**, not in resources. Handlers receive it as a parameter with a default pointing at the real implementation:

```python
def create_star(cmd: CreateStar, uow: AbstractUnitOfWork = SqlAlchemyUnitOfWork()):
    with uow:
        star = Star(id=cmd.id, name=cmd.name)
        uow.stars.add(star)
        uow.commit()
```

The message bus calls handlers with their default UoW. Tests pass `FakeUnitOfWork()` explicitly. Resources never hold or reference a UoW.

---

## Reads — Repository Only

List and retrieve operations go through `self.repo`. The repository handles filtering, pagination, and eager loading for `?include=`:

```python
def list(self):
    return self.repo.list(
        inclusions=self.inclusions,
        context=self.context,
    )

def retrieve(self, id):
    return self.repo.get(id, context=self.context)
```

The `context` dict carries request-scoped values (e.g. the authenticated user) that the repository uses in `get_where()`.

---

## No `self.tasks`

There is no `tasks` list on `Resource`. There is no `BackgroundTasks` parameter on route handlers.

Post-commit side effects are handled by event handlers registered on the message bus, triggered by domain events emitted during the command handler.

---

## The Factories

Three factory functions cover the common cases. They are always called separately — commands, handlers, and resource are independent objects that the application wires together via the bus.

### `build_commands`

Generates frozen command and event dataclasses from the `Db` model and Pydantic schemas. Can be called from anywhere, including `domain/`.

```python
from fastapi_resources.domain import build_commands

GalaxyCommands = build_commands(
    Db=Galaxy,
    Create=GalaxyCreate,
    Update=GalaxyUpdate,
)
# Commands (intent, in):
# GalaxyCommands.Create  →  CreateGalaxy(id, name, ...)
# GalaxyCommands.Update  →  UpdateGalaxy(id, name?, ...)
# GalaxyCommands.Delete  →  DeleteGalaxy(id)
#
# Events (fact, out):
# GalaxyCommands.Created  →  GalaxyCreated(id)
# GalaxyCommands.Updated  →  GalaxyUpdated(id)
# GalaxyCommands.Deleted  →  GalaxyDeleted(id)
```

Generated commands and events are plain frozen dataclasses. Commands can be dispatched from anywhere — not just HTTP. Events can be subscribed to from anywhere.

To override an event with a richer payload, replace the attribute before registering handlers:

```python
@dataclass(frozen=True)
class GalaxyCreated(Event):
    id: int
    name: str

GalaxyCommands.Created = GalaxyCreated
```

### `build_handlers`

Generates default CRUD handler functions from the commands and a UoW. Lives in the service layer.

```python
from fastapi_resources.handlers import build_handlers

GalaxyHandlers = build_handlers(
    Db=Galaxy,
    commands=GalaxyCommands,
    uow=default_uow,
)
# GalaxyHandlers.create  →  create_galaxy(cmd: CreateGalaxy, uow=default_uow)
# GalaxyHandlers.update  →  update_galaxy(cmd: UpdateGalaxy, uow=default_uow)
# GalaxyHandlers.delete  →  delete_galaxy(cmd: DeleteGalaxy, uow=default_uow)
```

Each generated handler emits the corresponding event from `commands` by appending it to the entity's `domain_events` list before `uow.commit()`. The UoW drains `domain_events` after commit and the bus queues them for dispatch.

### `build_sqlalchemy_resource`

Generates the HTTP layer only — repository, reads, and write dispatch. Takes no bus argument.

```python
from fastapi_resources.resources import build_sqlalchemy_resource

GalaxyResource = build_sqlalchemy_resource(
    Db=Galaxy,
    Read=GalaxyRead,
    Create=GalaxyCreate,
    Update=GalaxyUpdate,
    commands=GalaxyCommands,
)
```

### Bus Registration

Registration is always explicit. The application wires commands to handlers after all three factories have run.

```python
# Register individually:
bus.register(GalaxyCommands.Create, GalaxyHandlers.create)
bus.register(GalaxyCommands.Update, GalaxyHandlers.update)
bus.register(GalaxyCommands.Delete, GalaxyHandlers.delete)

# Or use the shorthand:
bus.register_resource(GalaxyCommands, GalaxyHandlers)
```

There are three levels of customisation, in increasing order of explicitness:

**1. Factory parameters** — for simple overrides:
```python
class GalaxyRepo(build_sqlalchemy_repo(Galaxy)):
    def get_where(self, method):
        return [Galaxy.owner_id == self.context["user_id"]]

GalaxyResource = build_sqlalchemy_resource(..., Repo=GalaxyRepo, commands=GalaxyCommands)
```

**2. Custom handler** — for business logic that the default handler can't express:
```python
def create_galaxy(cmd: GalaxyCommands.Create, uow=default_uow):
    with uow:
        # custom logic here
        ...

bus.register(GalaxyCommands.Create, create_galaxy)  # replaces the generated default
```

**3. Full resource class** — for complex write shapes or non-standard dispatch:
```python
class StarResource(SQLAlchemyResource[Star]):
    Repo = StarRepo
    Read = StarRead
    commands = StarCommands

    def create(self, attributes, relationships) -> Star:
        star_id = generate_id()
        self.messagebus_handle(StarCommands.Create(id=star_id, ...))
        return self.repo.get(star_id)
```

---

## Error Mapping

Domain exceptions are mapped to HTTP responses at the router level. Handlers raise domain exceptions; resources do not catch them. The mapping table is application-defined and registered with the router at startup.

```python
# In JSONAPIResourceRoute.get_route_handler:
except DomainException as exc:
    response = JSONResponse(status_code=400, content=parse_exception(exc))
except NotFound:
    response = JSONResponse(status_code=404, ...)
```

---

## What This Library Owns

- **`MessageBus`** — command/event routing, queue draining, fail-loud/fail-silent semantics
- **`build_sqlalchemy_repo(Db)`** — repository factory with full read/write capability
- **`build_sqlalchemy_resource(...)`** — full stack factory: repo + commands + handlers + resource class
- **JSON:API serialization** — `build_resource_object`, `build_response`, `build_document_links`
- **Relationship resolution** — `get_relationships()`, `get_related()`, `_zipped_inclusions_with_resource()`
- **Schema introspection** — `get_relationships_from_schema()`, association proxy support
- **Pagination** — `Paginator` classes, cursor/limit handling
- **`Resource.registry`** — `Db` class → Resource class lookup
- **Mixin composition** — `RetrieveResourceMixin`, `ListResourceMixin`, `CreateResourceMixin`, etc.

---

## Testing

Resources are testable without an HTTP server by instantiating them with a fake repository and a spy for the message bus handle:

```python
def test_create_dispatches_command():
    repo = FakeStarRepository()
    dispatched = []

    resource = StarResource(
        session=FakeSession(),
        messagebus_handle=lambda cmd: dispatched.append(cmd),
        context={"user_id": some_uuid},
    )
    resource.create(attributes={"name": "Sirius"}, relationships={})

    assert isinstance(dispatched[0], CreateStar)
    assert dispatched[0].name == "Sirius"
```

Handlers are testable independently with `FakeUnitOfWork()`, without touching the resource or HTTP layer.
