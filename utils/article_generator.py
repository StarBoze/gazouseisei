"""
Article Generator module for creating articles from outlines
"""
import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple

from .api_client import APIClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArticleGenerator:
    def __init__(self, api_client: APIClient, max_concurrent: int = 5):
        """
        Initialize article generator
        
        Args:
            api_client: APIClient instance for making API calls
            max_concurrent: Maximum number of concurrent article generation tasks
        """
        self.api_client = api_client
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def generate_section(self, 
                            section_index: int,
                            heading: str, 
                            subheadings: List[str],
                            keyword: str,
                            target_audience: str,
                            section_callback=None) -> Tuple[int, str]:
        """
        Generate a single section of the article
        
        Args:
            section_index: Index of the section (for tracking)
            heading: Main heading for this section
            subheadings: List of subheadings for this section
            keyword: Main article keyword/topic
            target_audience: Description of target audience
            
        Returns:
            Tuple of (section_index, generated_content)
        """
        async with self.semaphore:
            logger.info(f"Generating section {section_index + 1}: {heading}")
            
            # Create prompt for Claude API
            system_prompt = """
            You are an expert content writer specializing in comprehensive, high-quality long-form content.
            Your goal is to write a detailed, thorough, and engaging section of a larger article.
            Include practical examples, data points, and research where relevant.
            Create content that would be considered the definitive resource on this topic.
            """
            
            subheadings_text = "\n".join([f"- {sub}" for sub in subheadings])
            
            user_prompt = f"""
            Write a comprehensive section for an article about "{keyword}" targeting {target_audience}.
            
            # Section Heading:
            {heading}
            
            # Subheadings to Cover:
            {subheadings_text}
            
            Please write at least 10,000 words on this topic, covering each subheading thoroughly.
            Assume the reader has basic familiarity with the topic but wants in-depth knowledge.
            
            Use markdown formatting for headings, lists, and emphasis.
            Start with the main heading (# {heading}) followed by content about the general topic.
            Then include each subheading (## {subheadings[0]} etc.) with detailed content for each.
            
            Include practical tips, examples, case studies, and research findings where relevant.
            Make your writing engaging, informative, and valuable for {target_audience}.
            
            End your section with a brief summary and add <!--END_SECTION--> at the very end.
            """
            
            try:
                # Call OpenAI API to generate the section
                response = await self.api_client.call_text_generation_api(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=4000,  # GPT-4oの制限内の値（最大4096）
                    model="gpt-4o"
                )
                
                # Extract content from response
                choices = response.get('choices', [])
                if not choices or not isinstance(choices, list):
                    raise ValueError("Invalid response format from OpenAI API")
                    
                section_content = choices[0].get('message', {}).get('content', '')
                
                # Ensure the section ends with the required marker
                if "<!--END_SECTION-->" not in section_content:
                    section_content += "\n\n<!--END_SECTION-->"
                
                logger.info(f"Successfully generated section {section_index + 1} ({len(section_content)} chars)")
                
                # コールバックがあれば生成完了を通知
                if section_callback:
                    await section_callback(section_index, heading, section_content)
                    
                return section_index, section_content
                
            except Exception as e:
                logger.error(f"Error generating section {section_index + 1}: {e}")
                # Return a minimal section in case of error
                error_section = f"""
                # {heading}
                
                *Content generation for this section encountered an error. This is a placeholder.*
                
                ## {subheadings[0] if subheadings else 'Overview'}
                
                This section was meant to cover important aspects of {heading} related to {keyword}.
                
                ## {subheadings[1] if len(subheadings) > 1 else 'Additional Information'}
                
                Further information would have been provided here.
                
                <!--END_SECTION-->
                """
                return section_index, error_section
    
    async def generate_all_sections(self, 
                                 outline: Dict[str, List[Dict[str, Any]]],
                                 keyword: str,
                                 target_audience: str,
                                 progress_callback=None,
                                 section_callback=None) -> List[Tuple[int, str]]:
        """
        Generate all article sections from the outline
        
        Args:
            outline: Article outline with headings and subheadings
            keyword: Main article keyword/topic
            target_audience: Description of target audience
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of tuples (section_index, section_content) sorted by index
        """
        logger.info(f"Starting generation of {len(outline['outline'])} article sections")
        
        # Create tasks for all sections
        tasks = []
        for i, section in enumerate(outline['outline']):
            heading = section['heading']
            subheadings = section['subheadings']
            
            # Create a task for each section
            task = asyncio.create_task(
                self.generate_section(i, heading, subheadings, keyword, target_audience, section_callback)
            )
            tasks.append(task)
        
        # Process tasks with progress reporting
        results = []
        for future in asyncio.as_completed(tasks):
            section_index, content = await future
            results.append((section_index, content))
            
            # Report progress if callback provided
            if progress_callback:
                progress = len(results) / len(tasks)
                progress_callback(progress, f"Generated section {section_index + 1}/{len(tasks)}")
                
            logger.info(f"Completed {len(results)}/{len(tasks)} sections")
        
        # Sort results by section index
        results.sort(key=lambda x: x[0])
        return results
        
    async def save_sections_to_files(self, 
                                  sections: List[Tuple[int, str]], 
                                  output_dir: str) -> List[str]:
        """
        Save generated sections to individual files
        
        Args:
            sections: List of tuples (section_index, section_content)
            output_dir: Directory to save files
            
        Returns:
            List of saved file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        file_paths = []
        
        for section_index, content in sections:
            file_path = os.path.join(output_dir, f"section_{section_index + 1:02d}.md")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            file_paths.append(file_path)
            logger.info(f"Saved section {section_index + 1} to {file_path}")
            
        return file_paths
        
    def combine_sections(self, sections: List[Tuple[int, str]]) -> str:
        """
        Combine all sections into a single document
        
        Args:
            sections: List of tuples (section_index, section_content)
            
        Returns:
            Combined article content
        """
        # Sort sections by index to ensure correct order
        sorted_sections = sorted(sections, key=lambda x: x[0])
        
        # Concatenate all section content
        combined_content = ""
        for _, content in sorted_sections:
            # Remove the END_SECTION marker when combining
            section_content = content.replace("<!--END_SECTION-->", "")
            combined_content += section_content + "\n\n"
            
        return combined_content
