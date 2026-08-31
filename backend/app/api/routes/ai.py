from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.ai import AIChatRequest, AIChatResponse
from app.schemas.common import ApiResponse
from app.services.access import ensure_elder_access, get_owned_elder
from app.services.deepseek import call_deepseek

router = APIRouter()


@router.post("/ai/chat", response_model=ApiResponse[AIChatResponse])
async def chat_with_ai(
    payload: AIChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AIChatResponse]:
    if payload.elder_id is not None:
        elder = ensure_elder_access(db, current_user, payload.elder_id)
    elif current_user.role == "elder":
        elder = get_owned_elder(db, current_user)
    else:
        elder = None

    context = ""
    if elder is not None:
        display_name = payload.elder_name or elder.name
        context = f"当前服务对象是老人 {display_name}。请始终使用这个称呼，不要自行改成其他姓名或称谓。"
    prompt = (
        "你是银发独游的行程助手。请用简短、友善、易懂的中文回答，"
        "涉及修改或上传行程时先给出方案并等待确认，不要假装已经完成上传。"
        f"{context}\n用户说：{payload.message}"
    )
    reply, model = await call_deepseek(prompt)
    return ApiResponse(data=AIChatResponse(reply=reply, model=model))
