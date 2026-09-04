from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from app.model_benchmark_models import BenchmarkBatchResponse, BenchmarkCatalog, BenchmarkRunRequest
from app.model_benchmark_pricing import RegistryError
from app.model_benchmark_service import ModelBenchmarkService, catalog, validate_selections

router = APIRouter(prefix="/api/v1/model-benchmark")
_service = ModelBenchmarkService()


def get_model_benchmark_service() -> ModelBenchmarkService:
    return _service


@router.get("/catalog", response_model=BenchmarkCatalog)
async def get_catalog() -> BenchmarkCatalog:
    try:
        return catalog()
    except RegistryError:
        raise HTTPException(status_code=503, detail="Конфигурация моделей или тарифов недоступна.") from None


@router.post("/run", response_model=BenchmarkBatchResponse)
async def run_benchmark(
    request: BenchmarkRunRequest,
    response: Response,
    service: ModelBenchmarkService = Depends(get_model_benchmark_service),
) -> BenchmarkBatchResponse:
    try:
        validate_selections(request)
    except RegistryError:
        raise HTTPException(status_code=503, detail="Конфигурация моделей или тарифов недоступна.") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="Выберите модели из каталога backend.") from None
    request_id = uuid4().hex[:12]
    response.headers["X-Request-ID"] = request_id
    return await service.run(request, request_id)
