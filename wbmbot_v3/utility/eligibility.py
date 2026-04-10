from wbmbot_v3.utility import misc_operations

EligibilityDecision = tuple[bool, str | None]


def evaluate_flat_eligibility(flat_elem, flat_obj, user_profile) -> EligibilityDecision:
    """
    Evaluate whether a flat should be processed for the given user profile.
    """

    excluded, keywords = misc_operations.contains_filter_keywords(
        flat_elem,
        user_profile.exclude,
    )
    if excluded:
        joined_keywords = ", ".join(str(keyword) for keyword in keywords)
        return False, f"it contains exclude keyword(s) --> {joined_keywords}"

    if flat_obj.wbs and not user_profile.wbs:
        return False, "it requires WBS and your profile has no WBS"

    flat_rent = misc_operations.convert_rent(flat_obj.total_rent)
    if not misc_operations.verify_flat_rent(flat_rent, user_profile.flat_rent_below):
        return (
            False,
            "the rent doesn't match our criteria --> "
            f"Flat Rent: {flat_rent} EUR | "
            f"User wants it below: {user_profile.flat_rent_below} EUR",
        )

    flat_size = misc_operations.convert_size(flat_obj.size)
    if not misc_operations.verify_flat_size(flat_size, user_profile.flat_size_above):
        return (
            False,
            "the size doesn't match our criteria --> "
            f"Flat Size: {flat_size} m2 | "
            f"User wants it above: {user_profile.flat_size_above} m2",
        )

    flat_rooms = misc_operations.get_zimmer_count(flat_obj.rooms)
    if not misc_operations.verify_flat_rooms(flat_rooms, user_profile.flat_rooms_above):
        return (
            False,
            "the rooms don't match our criteria --> "
            f"Flat Rooms: {flat_rooms} | "
            f"User wants it above: {user_profile.flat_rooms_above}",
        )

    return True, None
