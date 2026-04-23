def get_profile_params(request):
    """
    Extract profile parameters from request, handling both 'profiles' and 'profiles[]' parameter names.

    Parameters
    ----------
    request : Request object
        The incoming request object containing query parameters.

    Returns
    -------
    list or None
        List of profile values if present, None otherwise.
    """
    # Try to get profiles from either 'profiles' or 'profiles[]' parameters
    profiles = request.query_params.getlist("profiles") or request.query_params.getlist("profiles[]")

    if profiles:
        return profiles
    return None


def handle_profile_params(profiles_param):
    """
    Handle profile parameters consistently for both 'profiles' and 'profiles[]' parameter names.

    Parameters
    ----------
    profiles_param : list
        List of profile names from query parameters.

    Returns
    -------
    list
        Normalized list of profile names.
    """
    if not profiles_param:
        return []
    return profiles_param
