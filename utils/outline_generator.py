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
                            image_style: str,
                            num_main_headings: int = 30,
                            num_sub_headings: int = 2) -> Dict[str, List[Dict[str, Any]]]:
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
        
        # Create prompt for API
        system_prompt = f"""
        You are an expert content strategist and SEO specialist. You will create a comprehensive outline for a very 
        long-form article that will thoroughly cover all aspects of the provided topic.
        
        You will generate exactly {num_main_headings} main headings and exactly {num_sub_headings} subheadings under each main heading.
        """
        
        user_prompt = f"""
        Create a comprehensive outline for an article about "{keyword}" targeting {target_audience}.
        
        The outline should include:
        - Exactly {num_main_headings} main headings (numbered 1-{num_main_headings})
        - Exactly {num_sub_headings} subheadings under each main heading
        
        Each heading should explore a different aspect of "{keyword}" and be designed to engage {target_audience}.
        
        Organize the topics in a logical progression, from introductory concepts to advanced applications.
        
        VERY IMPORTANT: Return your response in valid JSON format as follows:
        {{
            "outline": [
                {{
                    "heading": "Main Heading 1",
                    "subheadings": ["Subheading 1.1", "Subheading 1.2", ...]
                }},
                ...and so on for all {num_main_headings} headings
            ]
        }}
        
        Ensure all JSON is valid and properly escaped.
        """
        
        try:
            # Call OpenAI API to generate outline
            response = await self.api_client.call_text_generation_api(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=8000,
                model="gpt-4o"
            )
            
            # Extract and parse JSON from response
            choices = response.get('choices', [])
            if not choices or not isinstance(choices, list):
                raise ValueError("Invalid response format from OpenAI API")
                
            text_content = choices[0].get('message', {}).get('content', '{}')
            
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
                        raise ValueError("Could not extract JSON from OpenAI response")
            
            # Validate the outline structure
            if "outline" not in outline_data or not isinstance(outline_data["outline"], list):
                raise ValueError("Invalid outline structure in response")
                
            # Ensure exactly num_main_headings main headings
            if len(outline_data["outline"]) != num_main_headings:
                logger.warning(f"Expected {num_main_headings} headings, but got {len(outline_data['outline'])}. Adjusting...")
                
                # If fewer than expected, pad with defaults
                if len(outline_data["outline"]) < num_main_headings:
                    for i in range(len(outline_data["outline"]), num_main_headings):
                        default_subheadings = [f"Aspect {j+1} of Topic {i+1}" for j in range(num_sub_headings)]
                        outline_data["outline"].append({
                            "heading": f"Additional Topic {i+1} on {keyword}",
                            "subheadings": default_subheadings
                        })
                # If more than expected, truncate
                elif len(outline_data["outline"]) > num_main_headings:
                    outline_data["outline"] = outline_data["outline"][:num_main_headings]
            
            # Ensure each heading has exactly num_sub_headings subheadings
            for i, section in enumerate(outline_data["outline"]):
                if "subheadings" not in section or not isinstance(section["subheadings"], list):
                    # 何も設定されていない場合はデフォルトの小見出しを追加
                    default_subheadings = [f"Aspect {j+1} of {section['heading']}" for j in range(num_sub_headings)]
                    outline_data["outline"][i]["subheadings"] = default_subheadings
                elif len(section["subheadings"]) != num_sub_headings:
                    if len(section["subheadings"]) < num_sub_headings:
                        # 少ない場合は追加
                        heading = section["heading"]
                        while len(section["subheadings"]) < num_sub_headings:
                            section["subheadings"].append(f"Additional Aspect {len(section['subheadings'])+1} of {heading}")
                    elif len(section["subheadings"]) > num_sub_headings:
                        # 多い場合は切り詰め
                        section["subheadings"] = section["subheadings"][:num_sub_headings]
            
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
            
            # Generate remaining default headings
            for i in range(1, num_main_headings):
                default_subheadings = [f"Key Concept {i}.{j+1}" for j in range(num_sub_headings)]
                default_outline["outline"].append({
                    "heading": f"Topic {i}: Important Aspect of {keyword}",
                    "subheadings": default_subheadings
                })
                
            return default_outline
