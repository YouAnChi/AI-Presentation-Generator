"""图片生成（Image Generator）智能体：根据文本提示生成幻灯片配图。

核心职责：
- 接收包含 `prompt` 与 `title` 的 JSON，请求生成图片；
- 当前示例用 PIL 生成占位图，真实场景可替换为 DALL·E/Midjourney/Stable Diffusion；
- 返回图片的文件路径，供构建阶段插入到 PPT 中。

实现要点：
- 保证输出目录存在，文件名基于标题与随机数避免冲突；
- 在图像上写入标题与提示的摘要，便于调试与确认；
- 异常时返回错误文本，不阻断上游流程。
"""

import json
import logging
import os
import random
from typing import AsyncIterable, Any
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from ai_ppt.common.utils import get_logger
from ai_ppt.common.base_agent import BaseAgent
from a2a.types import AgentCard

logger = get_logger(__name__)

class ImageGeneratorAgent(BaseAgent):
    """图片生成智能体：返回可插入到 PPT 的图片路径。"""
    def __init__(self):
        super().__init__(
            agent_name="PPT Image Generator",
            description="Generates images for presentation slides based on prompts."
        )
        # 确保输出目录存在
        self.output_dir = Path("generated_images")
        self.output_dir.mkdir(exist_ok=True)

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        """流式生成图片：接收 `prompt` 与 `title`，返回图片路径。"""
        logger.info(f"Received request: {query}")
        
        try:
            # 预期输入为 JSON，包含 `prompt` 与 `title`
            data = json.loads(query)
            prompt = data.get("prompt", "")
            title = data.get("title", "Slide Image")
            
            logger.info(f"Generating image for: {title}")
            
            # 生成图片（占位实现：使用 PIL）。
            # 真实场景下可调用 DALL·E/Midjourney/Stable Diffusion API。
            image_path = self._generate_mock_image(title, prompt)
            
            logger.info(f"Image generated at: {image_path}")
            
            # 返回 JSON，包含图片路径
            result = {"image_path": str(image_path)}
            yield self.format_response(json.dumps(result))
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            yield self.format_response(f"Error: {e}")

    def _generate_mock_image(self, title: str, prompt: str) -> str:
        """使用 PIL 生成占位图，替代真实 AI 制图以便演示。"""
        # Create a random background color
        color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
        img = Image.new('RGB', (1024, 768), color=color)
        d = ImageDraw.Draw(img)
        
        # 尝试加载系统字体，失败时回退默认字体
        try:
            font = ImageFont.truetype("Arial.ttf", 40)
        except IOError:
            font = ImageFont.load_default()
            
        # 写入标题摘要
        d.text((50, 50), f"Image for: {title[:30]}...", fill=(255, 255, 255), font=font)
        
        # 写入提示词摘要（简单截断展示）
        d.text((50, 150), f"Prompt: {prompt[:100]}...", fill=(255, 255, 255), font=font)
        
        # 水印标注占位生成
        d.text((800, 700), "AI Generated Placeholder", fill=(200, 200, 200), font=font)

        # 保存文件：标题作文件名前缀，随机数避免重名
        filename = f"{title.replace(' ', '_')[:20]}_{random.randint(1000, 9999)}.png"
        filepath = self.output_dir / filename
        img.save(filepath)
        
        # 返回绝对路径，便于跨进程引用
        return str(filepath.absolute())

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        """生成当前智能体的 AgentCard，并声明其工具与标签。"""
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "generate_image",
                "name": "Generate Slide Image",
                "description": "Generates an image file based on a text prompt",
                "tags": ["image", "generation", "dalle"],
                "examples": ["Generate an image of a futuristic city"]
            }
        ]
        return card

if __name__ == "__main__":
    import click
    from ai_ppt.common.server_utils import start_agent_server
    
    @click.command()
    @click.option("--host", default="localhost")
    @click.option("--port", default=10204)
    def main(host, port):
        # 启动 Image Generator 的 A2A 服务端
        agent = ImageGeneratorAgent()
        start_agent_server(agent, host, port)
        
    main()
