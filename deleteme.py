from typing import ClassVar, Generic, Optional, Protocol, TypeVar

_MT_co = TypeVar("_MT_co", covariant=True)


class GenericAPIView:
    queryset: _MT_co

    def get_object(self) -> _MT_co:
        ...


class Foo:
    pass


class What(GenericAPIView):
    queryset: Foo


w = What()
w.queryset
a = w.get_object()


_IN = TypeVar("_IN", bound=type)  # Instance Type


# class SerializerProtocol(Protocol[_IN]):
#     instance: _IN


class BaseSerializer:
    def __init__(
        self,
        instance,
    ):
        self.instance = instance

    def update(self):
        return self.instance()


class FooSerializer(BaseSerializer):
    def __init__(self):
        self.instance = Foo

    # def update(self):
    #     return self.instance()


b = BaseSerializer(Foo)
b.instance
b.update()


f = FooSerializer()
f.instance
f.update()
