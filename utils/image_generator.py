"""
Image Generator module for creating images for article sections
"""
import os
import logging
import asyncio
import aiofiles
import httpx
from PIL import Image
from io import BytesIO
from typing import Dict, List, Any, Optional, Tuple, Union

from .api_client import APIClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageGenerator:
    def __init__(self, api_client: APIClient, max_concurrent: int = 10):
        """
        Initialize image generator
        
        Args:
            api_client: APIClient instance for making API calls
            max_concurrent: Maximum number of concurrent image generation tasks
        """
        self.api_client = api_client
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def generate_section_summary(self, 
                                    section_index: int,
                                    heading: str, 
                                    section_content: str) -> str:
        """
        Generate a summary of the section for image generation
        
        Args:
            section_index: Index of the section (for tracking)
            heading: Main heading for this section
            section_content: Content of the section
            
        Returns:
            Summary text for image generation
        """
        logger.info(f"Generating summary for section {section_index + 1}: {heading}")
        
        # Truncate section content if too long
        max_content_length = 8000
        content_for_summary = section_content[:max_content_length]
        if len(section_content) > max_content_length:
            content_for_summary += "..."
        
        # Create prompt for OpenAI API
        prompt = f"""
        Please summarize the key visual elements from this article section to create a detailed image prompt.
        
        Section Title: {heading}
        
        Content: ```
        {content_for_summary}
        ```
        
        Create a detailed, visual image prompt (200-300 words) that captures the essence of this section.
        Focus on visual elements, scenery, objects, people, colors, mood, and style.
        The prompt should be highly descriptive and specific to guide an AI image generator.
        DO NOT use terms like "an image of" or "a picture showing" in your response.
        Just provide the direct, detailed visual description.
        """
        
        try:
            # Call OpenAI API to generate the summary
            response = await self.api_client.call_openai_api(
                prompt=prompt,
                model="gpt-4o",
                max_tokens=1000
            )
            
            # Extract the summary from the response
            choices = response.get('choices', [])
            if not choices:
                raise ValueError("Invalid response format from OpenAI API")
                
            summary = choices[0].get('message', {}).get('content', '')
            
            logger.info(f"Successfully generated image prompt for section {section_index + 1}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating image prompt for section {section_index + 1}: {e}")
            # Return a simple image prompt in case of error
            return f"A detailed conceptual illustration representing {heading} with elements relevant to the topic, featuring professional visual style with clear symbols and meaningful imagery"
    
    async def generate_image(self, 
                          section_index: int,
                          heading: str, 
                          image_prompt: str,
                          image_style: str,
                          output_dir: str) -> Tuple[int, str]:
        """
        Generate an image for a section
        
        Args:
            section_index: Index of the section (for tracking)
            heading: Main heading for this section
            image_prompt: Image generation prompt
            image_style: Style preference (natural, vivid, etc.)
            output_dir: Directory to save the generated image
            
        Returns:
            Tuple of (section_index, image_path)
        """
        async with self.semaphore:
            logger.info(f"Generating image for section {section_index + 1}: {heading}")
            
            # Create final image prompt
            final_prompt = f"{image_prompt}. Style: {image_style}. Title: {heading}"
            
            try:
                # Call OpenAI's DALL-E API to generate the image
                response = await self.api_client.generate_image(
                    prompt=final_prompt,
                    size="1024x1024",
                    style="natural" if image_style.lower() == "natural" else "vivid"
                )
                
                # Extract the image URL from the response
                if not response or 'data' not in response or not response['data']:
                    raise ValueError("Invalid response format from DALL-E API")
                    
                image_url = response['data'][0].get('url')
                if not image_url:
                    raise ValueError("No image URL in DALL-E response")
                
                # Ensure output directory exists
                os.makedirs(output_dir, exist_ok=True)
                
                # Download the generated image
                async with httpx.AsyncClient() as client:
                    img_response = await client.get(image_url)
                    img_response.raise_for_status()
                    
                    # Save the image
                    image_filename = f"section_{section_index + 1:02d}.png"
                    image_path = os.path.join(output_dir, image_filename)
                    
                    # Process and save image
                    img = Image.open(BytesIO(img_response.content))
                    img.save(image_path, format="PNG")
                    
                logger.info(f"Successfully generated and saved image for section {section_index + 1} to {image_path}")
                return section_index, image_path
                
            except Exception as e:
                logger.error(f"Error generating image for section {section_index + 1}: {e}")
                # Return placeholder in case of error
                return section_index, ""
    
    async def generate_all_images(self, 
                               sections: List[Tuple[int, str]],
                               headings: List[str],
                               image_style: str,
                               output_dir: str,
                               progress_callback=None) -> List[Tuple[int, str]]:
        """
        Generate images for all article sections
        
        Args:
            sections: List of tuples (section_index, section_content)
            headings: List of section headings
            image_style: Style preference for images
            output_dir: Directory to save generated images
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of tuples (section_index, image_path) sorted by index
        """
        logger.info(f"Starting generation of {len(sections)} images")
        
        # Create tasks for section summaries and image generation
        summary_tasks = []
        for section_index, content in sections:
            if section_index < len(headings):
                heading = headings[section_index]
                task = asyncio.create_task(
                    self.generate_section_summary(section_index, heading, content)
                )
                summary_tasks.append((section_index, heading, task))
        
        # Wait for all summaries to complete
        image_tasks = []
        for section_index, heading, task in summary_tasks:
            try:
                image_prompt = await task
                image_task = asyncio.create_task(
                    self.generate_image(
                        section_index, heading, image_prompt, image_style, output_dir
                    )
                )
                image_tasks.append(image_task)
                
                # Report progress if callback provided
                if progress_callback:
                    summary_progress = (section_index + 1) / len(sections) * 0.5
                    progress_callback(summary_progress, f"Generated image prompt {section_index + 1}/{len(sections)}")
                    
            except Exception as e:
                logger.error(f"Error with summary for section {section_index + 1}: {e}")
        
        # Process image tasks with progress reporting
        results = []
        for future in asyncio.as_completed(image_tasks):
            section_index, image_path = await future
            results.append((section_index, image_path))
            
            # Report progress if callback provided
            if progress_callback:
                image_progress = 0.5 + (len(results) / len(sections) * 0.5)
                progress_callback(image_progress, f"Generated image {len(results)}/{len(sections)}")
                
            logger.info(f"Completed {len(results)}/{len(image_tasks)} images")
        
        # Sort results by section index
        results.sort(key=lambda x: x[0])
        return results
        
    def insert_images_into_markdown(self, 
                                 combined_markdown: str, 
                                 image_paths: List[Tuple[int, str]],
                                 base_path: str = "") -> str:
        """
        Insert images into the combined markdown document
        
        Args:
            combined_markdown: Combined article content
            image_paths: List of tuples (section_index, image_path)
            base_path: Optional base path for image references
            
        Returns:
            Markdown with images inserted
        """
        lines = combined_markdown.split("\n")
        result_lines = []
        current_section = 0
        image_added = [False] * len(image_paths)
        
        # Sort image paths by section index
        sorted_image_paths = sorted(image_paths, key=lambda x: x[0])
        
        for line in lines:
            result_lines.append(line)
            
            # Look for main headings (# Title) to insert images
            if line.startswith("# "):
                if current_section < len(sorted_image_paths):
                    section_index, image_path = sorted_image_paths[current_section]
                    
                    # If we have a valid image path for this section
                    if image_path and not image_added[section_index]:
                        # Get just the filename from the path
                        image_filename = os.path.basename(image_path)
                        image_ref = f"{base_path}{image_filename}" if base_path else image_filename
                        
                        # Insert image reference after the heading
                        result_lines.append("")
                        result_lines.append(f"![{line.lstrip('# ')}]({image_ref})")
                        result_lines.append("")
                        
                        image_added[section_index] = True
                
                current_section += 1
        
        return "\n".join(result_lines)
