from typing import Any, Callable, Dict, List, Optional, Union

from tartiflette.resolver import ResolverExecutorFactory
from tartiflette.types.enum import GraphQLEnumType
from tartiflette.types.helpers import (
    get_directive_implem_list,
    reduce_type,
    surround_with_directive,
)
from tartiflette.types.type import GraphQLType


class GraphQLField:
    """
    Field Definition

    A field is used in Object, Interfaces as its constituents.
    """

    def __init__(
        self,
        name: str,
        gql_type: Union[str, GraphQLType],
        arguments: Optional[Dict[str, "GraphQLArgument"]] = None,
        resolver: Optional[callable] = None,
        description: Optional[str] = None,
        directives: Optional[Dict[str, Optional[dict]]] = None,
        schema: Optional["GraphQLSchema"] = None,
    ) -> None:
        self.name = name
        self.gql_type = gql_type
        self.arguments = arguments or {}

        self._directives = directives
        self._schema = schema
        self.description = description or ""

        self.resolver = ResolverExecutorFactory.get_resolver_executor(
            resolver, self
        )
        self.subscribe = None
        self.parent_type = None

        # Introspection Attribute
        self.isDeprecated = False  # pylint: disable=invalid-name
        self._directives_implementations = None
        self._is_leaf = False
        self._is_enum = False
        self._reduced_type = None
        self._reduced_type_name = None
        self._introspection_directives = None

    @property
    def directives(self) -> List[Dict[str, Any]]:
        return self._directives_implementations

    @property
    def introspection_directives(self):
        return self._introspection_directives

    def __repr__(self) -> str:
        return (
            "{}(name={!r}, gql_type={!r}, arguments={!r}, "
            "resolver={!r}, description={!r}, directives={!r})".format(
                self.__class__.__name__,
                self.name,
                self.gql_type,
                self.arguments,
                self.resolver,
                self.description,
                self.directives,
            )
        )

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: Any) -> bool:
        return self is other or (
            type(self) is type(other)
            and self.name == other.name
            and self.gql_type == other.gql_type
            and self.arguments == other.arguments
            and self.resolver == other.resolver
            and self.directives == other.directives
        )

    # Introspection Attribute
    @property
    def kind(self) -> str:
        try:
            return self.gql_type.kind
        except AttributeError:
            pass
        return "FIELD"

    # Introspection Attribute
    @property
    def type(self) -> Union[str, GraphQLType]:
        if isinstance(self.gql_type, GraphQLType):
            return self.gql_type
        return self.schema.find_type(self.gql_type)

    # Introspection Attribute
    @property
    def args(self) -> List["GraphQLArgument"]:
        return list(self.arguments.values())

    @property
    def schema(self) -> "GraphQLSchema":
        return self._schema

    @property
    def is_leaf(self) -> bool:
        return self._is_leaf

    @property
    def is_enum(self) -> bool:
        return self._is_enum

    @property
    def reduced_type(self) -> "GraphQLType":
        return self._reduced_type

    def _compute_is_leaf(self) -> bool:
        try:
            if self._schema.find_scalar(self._reduced_type_name):
                return True
        except KeyError:
            pass

        try:
            if self._schema.find_enum(self._reduced_type_name):
                return True
        except KeyError:
            pass

        return False

    def bake(
        self,
        schema: "GraphQLSchema",
        parent_type: Any,
        custom_default_resolver: Optional[Callable],
    ) -> None:
        self._schema = schema
        self._reduced_type_name = reduce_type(self.gql_type)
        self._reduced_type = self._schema.find_type(self._reduced_type_name)
        self._directives_implementations = get_directive_implem_list(
            self._directives, self._schema
        )
        self._introspection_directives = surround_with_directive(
            None, self._directives_implementations, "on_introspection"
        )
        self.parent_type = parent_type

        self._is_leaf = self._compute_is_leaf()
        self._is_enum = isinstance(self._reduced_type, GraphQLEnumType)

        for arg in self.arguments.values():
            arg.bake(self._schema)

        self.resolver.bake(custom_default_resolver)
