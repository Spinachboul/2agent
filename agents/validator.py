from collections import Counter
from jsonschema import Draft202012Validator

from schemas.brd_schema import BRD_SCHEMA


class ValidatorAgent:
    REQUIREMENT_COLLECTIONS = (
        "business_requirements",
        "functional_requirements",
        "non_functional_requirements",
    )

    def run(self, generated: dict) -> tuple[dict, dict]:
        issues = []

        for error in Draft202012Validator(
            BRD_SCHEMA
        ).iter_errors(generated):
            issues.append({
                "severity": "error",
                "type": "schema",
                "path": "/" + "/".join(map(str, error.absolute_path)),
                "message": error.message,
            })

        ids = []
        all_ids = set()

        for collection in self.REQUIREMENT_COLLECTIONS:
            items = generated.get(collection, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    issues.append({
                        "severity": "error",
                        "type": "invalid_requirement",
                        "message": f"Invalid entry in {collection}",
                    })
                    continue

                req_id = item.get("id")
                if not req_id:
                    issues.append({
                        "severity": "error",
                        "type": "missing_id",
                        "message": f"Requirement in {collection} has no ID",
                    })
                else:
                    ids.append(req_id)
                    all_ids.add(req_id)

                confidence = item.get("confidence")
                if (
                    not isinstance(confidence, (int, float))
                    or isinstance(confidence, bool)
                    or not 0 <= confidence <= 1
                ):
                    issues.append({
                        "severity": "error",
                        "type": "invalid_confidence",
                        "requirement_id": req_id,
                        "message": "Confidence must be between 0 and 1",
                    })

        duplicates = [
            req_id for req_id, count in Counter(ids).items()
            if count > 1
        ]
        for req_id in duplicates:
            issues.append({
                "severity": "error",
                "type": "duplicate_requirement",
                "requirement_id": req_id,
                "message": "Requirement ID appears more than once",
            })

        # Add reference checks for acceptance criteria, dependencies,
        # workflow IDs, and source_refs based on your canonical schema.
        # Validate source_refs against the extractor's actual source IDs.

        error_count = sum(
            issue["severity"] == "error" for issue in issues
        )
        warning_count = sum(
            issue["severity"] == "warning" for issue in issues
        )

        # Transparent structural score, not an LLM confidence estimate.
        score = max(0.0, 100.0 - 10.0 * error_count
                    - 2.0 * warning_count)

        report = {
            "validation_score": score,
            "is_valid": error_count == 0,
            "issues": issues,
            "recommendations": [
                f"Resolve {error_count} validation errors."
            ] if error_count else [],
        }

        validated = generated if report["is_valid"] else {}
        return validated, report