"""
API Client for interacting with OpenAI API
"""
import os
import json
import logging
import httpx
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize API client with OpenAI API key
        
        Args:
            openai_api_key: OpenAI API key (can also be set via OPENAI_API_KEY env var)
        """
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.openai_api_key:
            logger.warning("OpenAI API key not provided. API calls will fail.")
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=60))
    async def call_text_generation_api(self, prompt: str, max_tokens: int = 4000, 
                           system_prompt: Optional[str] = None, model: str = "gpt-4o") -> Dict[Any, Any]:
        """
        Call the OpenAI API for text generation with retry logic for rate limits
        
        Args:
            prompt: The user prompt to send to the model
            max_tokens: Maximum tokens in response
            system_prompt: Optional system prompt to guide the model
            model: OpenAI model to use (default: gpt-4o)
            
        Returns:
            Dict containing the API response
        """
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
            
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }
            
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded, retrying...")
                raise
            logger.error(f"HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def generate_image(self, prompt: str, size: str = "1024x1024", 
                          style: str = "natural") -> Dict[Any, Any]:
        """
        Generate an image using OpenAI's DALL-E
        
        Args:
            prompt: The image prompt
            size: Image size (default: 1024x1024)
            style: Image style (natural or vivid)
            
        Returns:
            Dict containing image URL and other response data
        """
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
            
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "dall-e-3",
            "prompt": prompt,
            "size": size,
            "style": style,
            "quality": "standard",
            "n": 1
        }
            
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded, retrying...")
                raise
            logger.error(f"HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise
