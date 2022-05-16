from functools import wraps


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


def map_exceptions(exceptions: dict[type[Exception], type[Exception]]):
    def _wrapper(f):
        @wraps(f)
        def _map_exceptions(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                for source_type in exceptions:
                    if isinstance(e, source_type):
                        target_class = exceptions[source_type]
                        raise target_class(str(e))

                raise

        return _map_exceptions

    return _wrapper
