from typing import TypeVar

# type variables
T = TypeVar("T")
U = TypeVar("U")

# covariant type variables
T_co = TypeVar("T_co", covariant=True)
U_co = TypeVar("U_co", covariant=True)
