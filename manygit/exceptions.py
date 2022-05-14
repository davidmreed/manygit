import typing as T


class ManygitException(Exception):
    pass


class NetworkError(ManygitException):
    pass


class NotFoundError(ManygitException):
    pass


class ConnectionException(ManygitException):
    pass


class VCSException(ManygitException):
    pass


def map_exceptions(exceptions: dict[T.Type[Exception], T.Type[Exception]]):
    def _map_exceptions(f, *args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            for source_type in exceptions:
                if isinstance(e, source_type):
                    target_class = exceptions[source_type]
                    raise target_class(str(e))

            raise

    return _map_exceptions
