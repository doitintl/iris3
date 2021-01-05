def cls_by_name(fully_qualified_classname):
    parts = fully_qualified_classname.split('.')
    module = '.'.join(parts[:-1])
    n = __import__(module)
    for comp in parts[1:]:
        n = getattr(n, comp)
    return n
