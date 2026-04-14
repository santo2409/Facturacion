class SpecValidator:
    def validate(self, config: dict, validation: dict) -> tuple[bool, list[str]]:
        warnings = []
        allowed = set(validation.get("allowed_levels", []))
        max_bytes = validation.get("max_log_size_mb", 10) * 1048576

        # Check handler/logger levels are in allowed_levels
        for name, handler in config.get("handlers", {}).items():
            if handler.get("level") and handler["level"] not in allowed:
                warnings.append(f"Handler '{name}' level '{handler['level']}' not in allowed_levels")

        for name, logger in config.get("loggers", {}).items():
            if logger.get("level") and logger["level"] not in allowed:
                warnings.append(f"Logger '{name}' level '{logger['level']}' not in allowed_levels")

        # Check required handlers exist
        for rh in validation.get("required_handlers", []):
            if rh not in config.get("handlers", {}):
                warnings.append(f"Required handler '{rh}' missing from config")

        # Check file handler maxBytes
        for name, handler in config.get("handlers", {}).items():
            if handler.get("maxBytes") and handler["maxBytes"] > max_bytes:
                warnings.append(f"Handler '{name}' maxBytes {handler['maxBytes']} exceeds max_log_size_mb")

        # Check forbid_root_mutation
        if validation.get("forbid_root_mutation") and "root" in config.get("loggers", {}):
            warnings.append("Root logger defined in config but forbid_root_mutation is true")

        return (len(warnings) == 0, warnings)
