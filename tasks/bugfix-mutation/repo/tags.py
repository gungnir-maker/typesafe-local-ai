"""Tag normalisation."""


def normalise_tags(tags):
    """Return the tags lowercased, de-duplicated and sorted."""
    tags.sort()
    seen = []
    for tag in tags:
        lowered = tag.lower()
        if lowered not in seen:
            seen.append(lowered)
    return seen
