from kaparoo.utils.singleton import singleton, Singleton, SingletonMeta


def test_decorator():
    @singleton
    class MyClass:
        pass

    instance1 = MyClass()
    instance2 = MyClass()

    assert instance1 is instance2


def test_class():
    class MyClass(Singleton):
        pass

    instance1 = MyClass()
    instance2 = MyClass()

    assert instance1 is instance2


def test_metaclass():
    class MyClass(metaclass=SingletonMeta):
        pass

    instance1 = MyClass()
    instance2 = MyClass()

    assert instance1 is instance2
