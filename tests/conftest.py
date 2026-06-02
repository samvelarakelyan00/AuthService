import sys
import jwt

# Force Pytest to find the warning class where it's looking for it
if not hasattr(jwt.exceptions, "InsecureKeyLengthWarning"):
    import jwt.warnings
    sys.modules["jwt.exceptions"].InsecureKeyLengthWarning = getattr(
        jwt.warnings, "InsecureKeyLengthWarning", UserWarning
    )
