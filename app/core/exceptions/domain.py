from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            message=f"{entity} not found",
            detail=f"{entity} with id '{identifier}' not found",
        )


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(message="Unauthorized", detail=detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(message="Forbidden", detail=detail)


class ConflictError(AppError):
    def __init__(self, entity: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{entity} already exists",
            detail=f"A {entity} with {field} '{value}' already exists",
        )


class ValidationError(AppError):
    def __init__(self, detail: str, field: str | None = None) -> None:
        message = f"Validation error: {field}" if field else "Validation error"
        super().__init__(message=message, detail=detail)


class FileProcessingError(AppError):
    def __init__(self, detail: str, filename: str | None = None) -> None:
        message = f"File processing failed: {filename}" if filename else "File processing failed"
        super().__init__(message=message, detail=detail)


class UnsupportedFileTypeError(FileProcessingError):
    def __init__(self, mime_type: str, filename: str | None = None) -> None:
        super().__init__(detail=f"Unsupported file type: {mime_type}", filename=filename)


class FileTooLargeError(FileProcessingError):
    def __init__(self, size_bytes: int, max_bytes: int, filename: str | None = None) -> None:
        super().__init__(
            detail=f"File size ({size_bytes} bytes) exceeds maximum ({max_bytes} bytes)",
            filename=filename,
        )


class ProcessingNotCompleteError(AppError):
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            message="Processing not complete",
            detail=f"{entity} '{identifier}' is still being processed",
        )


class LlmServiceError(AppError):
    def __init__(self, detail: str, model: str | None = None) -> None:
        message = f"LLM service error: {model}" if model else "LLM service error"
        super().__init__(message=message, detail=detail)


class EmbeddingServiceError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(message="Embedding service error", detail=detail)


class VectorStoreError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(message="Vector store error", detail=detail)


class RetrievalError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(message="Retrieval error", detail=detail)


class TokenBudgetExceededError(AppError):
    def __init__(self, current: int, limit: int) -> None:
        super().__init__(
            message="Token budget exceeded",
            detail=f"Current token count ({current}) exceeds budget ({limit})",
        )
