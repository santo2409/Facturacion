class NitCacheSaveError(Exception):
    """El caché de NITs no pudo persistir el lote (error técnico), a diferencia
    de los NITs omitidos por nombre duplicado, que `save_many` sí devuelve."""
