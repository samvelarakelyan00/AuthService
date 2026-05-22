from functools import lru_cache

from core.security import Security


"""
get_security is typically cached when the Security class
contains settings (for example, Argon2 parameters)
that are read from the config or AWS SSM.
The cache eliminates the need to initialize the settings object with each request.
"""
@lru_cache(maxsize=1)
def get_security_instance() -> Security:
    # Here will logic of getting security parameters from AWS parameter store
    # memory_cost=65536,
    # time_cost=3,
    # parallelism=4

    # ssm_params = get_ssm_parameters()
    # return Security(params=ssm_params)

    return Security()


# This function will used in Depends()
def get_security() -> Security:
    return get_security_instance()
