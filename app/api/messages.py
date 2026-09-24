import json
import asyncio
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from app.schemas.message import MessageRequest
from app.database.threads import get_thread_metadata, update_thread_metadata
from app.graph.graph import build_graph

router = APIRouter()


@router.post("/messages/stream")
async def stream_message(request: MessageRequest, background_tasks: BackgroundTasks):
    metadata = await asyncio.to_thread(get_thread_metadata, request.thread_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Thread not found")

    graph = build_graph()

    # Schedule the non-critical timestamp update in the background
    background_tasks.add_task(update_thread_metadata, request.thread_id)

    async def generate_response():
        config = {"configurable": {"thread_id": request.thread_id}}
        inputs = {"messages": [HumanMessage(content=request.message)]}

        sources = []

        try:
            # Stream tokens from the generate_answer node
            async for msg, meta in graph.astream(
                inputs, config=config, stream_mode="messages"
            ):
                if meta.get("langgraph_node") == "generate_answer":
                    if msg.content:
                        yield msg.content

            # After streaming, get the final state for sources
            final_state = await graph.aget_state(config)
            if final_state and final_state.values:
                sources = final_state.values.get("sources", [])

            # Send sources as a final JSON line
            if sources:
                yield "\n\n" + json.dumps({"sources": sources})

        except Exception as e:
            print(f"Error during streaming: {e}")
            yield ""

    return StreamingResponse(
        generate_response(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
