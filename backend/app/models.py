from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationControls(StrictModel):
    structured_output: bool = False
    max_output_tokens: int | None = Field(default=None, ge=1)
    finish_instruction: bool = False


class GenerateRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    controls: GenerationControls = Field(default_factory=GenerationControls)


class Ingredient(StrictModel):
    name: str
    weight_grams: int = Field(gt=0)
    order: int = Field(ge=1)


class RecipeStep(StrictModel):
    order: int = Field(ge=1)
    description: str


class Recipe(StrictModel):
    recipe_name: str
    ingredients: list[Ingredient]
    steps: list[RecipeStep]


class AppliedControls(StrictModel):
    structured_output: bool
    max_output_tokens: int | None
    finish_instruction: bool


class ErrorInfo(StrictModel):
    code: str
    message: str


class GenerateResponse(StrictModel):
    request_id: str | None = None
    content: str | None = None
    recipe: Recipe | None = None
    status: str
    output_tokens: int | None = None
    controls: AppliedControls
    incomplete_reason: str | None = None
    error: ErrorInfo | None = None


OpenAIStatus = Literal[
    "completed",
    "failed",
    "in_progress",
    "cancelled",
    "queued",
    "incomplete",
]
