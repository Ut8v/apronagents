"""The single audited wrapper over the git subprocess.

Every raw git invocation in Apron goes through this module, which is what
makes the no-real-remote invariant auditable in one place.
"""
