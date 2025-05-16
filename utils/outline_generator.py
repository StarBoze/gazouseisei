"""
Outline Generator module for creating article outlines
"""
import json
import logging
from typing import Dict, List, Any, Optional

from .api_client import APIClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OutlineGenerator:
    def __init__(self, api_client: APIClient):
        """
        Initialize outline generator
        
        Args:
            api_client: APIClient instance for making API calls
        """
        self.api_client = api_client
    
    async def generate_outline(self, 
                            keyword: str, 
                            target_audience: str, 
                            image_style: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate article outline with 30 main headings and 2 subheadings each
        
        Args:
            keyword: Main article keyword/topic
            target_audience: Description of target audience
            image_style: Preferred image style
            
        Returns:
            Dictionary containing main headings and subheadings
        """
        logger.info(f"Generating outline for keyword: {keyword}")
        
        # Create prompt for Claude API
        system_prompt = """
        You are an expert content strategist and SEO specialist. You will create a comprehensive outline for a very 
        long-form article (over 300,000 words) that will thoroughly cover all aspects of the provided topic.
        """
        
        user_prompt = f"""
        Create a comprehensive outline for a 300,000+ word article about "{keyword}" targeting {target_audience}.
        
        The outline should include:
        - Exactly 30 main headings (numbered 1-30)
        - Exactly 2 subheadings under each main heading
        
        Each heading should explore a different aspect of "{keyword}" and be designed to engage {target_audience}.
        
        Organize the topics in a logical progression, from introductory concepts to advanced applications.
        
        VERY IMPORTANT: Return your response in valid JSON format as follows:
        {{
            "outline": [
                {{
                    "heading": "Main Heading 1",
                    "subheadings": ["Subheading 1.1", "Subheading 1.2"]
                }},
                ...and so on for all 30 headings
            ]
        }}
        
        Ensure all JSON is valid and properly escaped.
        """
        
        try:
            # Call Claude API to generate outline
            response = await self.api_client.call_claude_api(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=8000
            )
            
            # Extract and parse JSON from response
            content = response.get('content', [])
            if not content or not isinstance(content, list):
                raise ValueError("Invalid response format from Claude API")
                
            text_content = content[0].get('text', '{}')
            
            # Try to extract JSON from the text content
            try:
                # First, try to parse the entire response as JSON
                outline_data = json.loads(text_content)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```json\n(.*?)\n```', text_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    outline_data = json.loads(json_str)
                else:
                    # Last resort, try to find any JSON-like structure
                    json_match = re.search(r'({.*})', text_content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        outline_data = json.loads(json_str)
                    else:
                        raise ValueError("Could not extract JSON from Claude response")
            
            # Validate the outline structure
            if "outline" not in outline_data or not isinstance(outline_data["outline"], list):
                raise ValueError("Invalid outline structure in response")
                
            # Ensure exactly 30 main headings
            if len(outline_data["outline"]) != 30:
                logger.warning(f"Expected 30 headings, but got {len(outline_data['outline'])}. Adjusting...")
                
                # If fewer than 30, pad with defaults
                if len(outline_data["outline"]) < 30:
                    for i in range(len(outline_data["outline"]), 30):
                        outline_data["outline"].append({
                            "heading": f"Additional Topic {i+1} on {keyword}",
                            "subheadings": [f"Aspect 1 of Topic {i+1}", f"Aspect 2 of Topic {i+1}"]
                        })
                # If more than 30, truncate
                elif len(outline_data["outline"]) > 30:
                    outline_data["outline"] = outline_data["outline"][:30]
            
            # Ensure each heading has exactly 2 subheadings
            for i, section in enumerate(outline_data["outline"]):
                if "subheadings" not in section or not isinstance(section["subheadings"], list):
                    outline_data["outline"][i]["subheadings"] = [
                        f"Key Aspect of {section['heading']}", 
                        f"Advanced Concepts in {section['heading']}"
                    ]
                elif len(section["subheadings"]) != 2:
                    if len(section["subheadings"]) < 2:
                        # Pad with defaults if fewer than 2
                        heading = section["heading"]
                        while len(section["subheadings"]) < 2:
                            section["subheadings"].append(f"Additional Aspect of {heading}")
                    elif len(section["subheadings"]) > 2:
                        # Truncate if more than 2
                        section["subheadings"] = section["subheadings"][:2]
            
            logger.info(f"Successfully generated outline with {len(outline_data['outline'])} main headings")
            return outline_data
            
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            # Return a default outline in case of error
            default_outline = {
                "outline": [
                    {
                        "heading": f"Understanding {keyword}: A Comprehensive Introduction",
                        "subheadings": [f"What is {keyword}?", f"Why {keyword} Matters for {target_audience}"]
                    }
                ]
            }
            
            # Generate 29 more default headings
            for i in range(1, 30):
                default_outline["outline"].append({
                    "heading": f"Topic {i}: Important Aspect of {keyword}",
                    "subheadings": [f"Key Concept {i}.1", f"Key Concept {i}.2"]
                })
                
            return default_outline
