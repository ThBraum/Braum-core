class SQLGateway:
    def execute_allowed_query(self, query: str) -> list[dict[str, object]]:
        return [
            {
                "query": query,
                "status": "executed",
            }
        ]
