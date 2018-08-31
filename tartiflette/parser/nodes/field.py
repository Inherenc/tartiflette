
import asyncio
from typing import Any, Callable, Dict, List
from uuid import uuid4

from tartiflette.executors.types import ExecutionContext, Info
from tartiflette.schema import GraphQLSchema
from tartiflette.types.exceptions.tartiflette import GraphQLError
from tartiflette.types.location import Location

from .node import Node


class NodeField(Node):
    def __init__(
        self,
        name: str,
        schema: GraphQLSchema,
        field_executor: Callable,
        location: Location,
        path: List[str],
        type_condition: str,
    ):
        super().__init__(path, "Field", location, name)
        # Execution
        self.schema = schema
        self.field_executor = field_executor
        self.arguments = {}
        self.type_condition = type_condition
        self.marshalled = {}
        self.uuid = str(uuid4())

    @property
    def cant_be_null(self) -> bool:
        return self.field_executor.cant_be_null

    @property
    def contains_not_null(self) -> bool:
        return self.field_executor.contains_not_null

    @property
    def shall_produce_list(self) -> bool:
        return self.field_executor.shall_produce_list

    def bubble_error(self):
        if self.cant_be_null is False:
            # mean i can be null
            if self.parent:
                self.parent.marshalled[self.name] = None
            else:
                self.marshalled = None
        else:
            if self.parent:
                self.parent.bubble_error()
            else:
                self.marshalled = None

    async def _execute_children(self, exec_ctx, request_ctx, result, coerced):
        # TODO also filter regarding OnType thingy
        coroutz = []
        if self.shall_produce_list:
            for index, raw in enumerate(result):
                for child in self.children:
                    coroutz.append(
                        child(
                            exec_ctx,
                            request_ctx,
                            parent_result=raw,
                            parent_marshalled=coerced[index],
                        )
                    )
        else:
            coroutz = [
                child(
                    exec_ctx,
                    request_ctx,
                    parent_result=result,
                    parent_marshalled=coerced,
                )
                for child in self.children
            ]

        await asyncio.gather(*coroutz, return_exceptions=False)

    async def __call__(
        self,
        exec_ctx: ExecutionContext,
        request_ctx: Dict[str, Any],
        parent_result=None,
        parent_marshalled=None,
    ) -> Any:

        raw, coerced = await self.field_executor(
            parent_result,
            self.arguments,
            request_ctx,
            Info(
                query_field=self,
                schema_field=self.field_executor.schema_field,
                schema=self.schema,
                path=self.path,
                location=self.location,
                execution_ctx=exec_ctx,
            ),
        )

        if parent_marshalled is not None:
            parent_marshalled[self.name] = coerced
        else:
            self.marshalled = coerced

        if isinstance(raw, Exception):
            gql_error = GraphQLError(str(raw), self.path, [self.location])
            if self.cant_be_null or self.contains_not_null:
                gql_error.user_message = "%s - %s is not nullable" % (
                    gql_error.message,
                    self.name,
                )
                if self.parent and self.cant_be_null:
                    self.parent.bubble_error()
            exec_ctx.add_error(gql_error)
        else:
            if self.children:
                await self._execute_children(
                    exec_ctx, request_ctx, result=raw, coerced=coerced
                )

    def __eq__(self, other):
        return self.uuid == other.uuid
