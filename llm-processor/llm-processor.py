import os
import json
import tiktoken
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class BusinessModelAnalyzer:
    def __init__(self, input_file: str = "scraped_data/final.md", output_dir: str = "analysis_output"):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )

    def read_content(self) -> str:
        """Read content from the markdown file"""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return ""

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string"""
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))

    def chunk_content(self, content: str, max_tokens: int = 100000) -> list[str]:
        """Split content into chunks of approximately max_tokens tokens"""
        encoding = tiktoken.encoding_for_model("gpt-4")
        tokens = encoding.encode(content)
        chunks = []
        current_chunk = []
        current_size = 0

        for token in tokens:
            if current_size >= max_tokens:
                chunk_text = encoding.decode(current_chunk)
                chunks.append(chunk_text)
                current_chunk = [token]
                current_size = 1
            else:
                current_chunk.append(token)
                current_size += 1

        if current_chunk:
            chunk_text = encoding.decode(current_chunk)
            chunks.append(chunk_text)

        return chunks

    def analyze_chunk(self, chunk: str, chunk_num: int, total_chunks: int) -> str:
        """Analyze a single chunk of content"""
        try:
            system_message = f"""
            You are a business analyst expert analyzing part {chunk_num} of {total_chunks} of a document.
            Focus on identifying key business model elements in this section, including:
            - Value propositions
            - Customer segments
            - Revenue streams
            - Resources and activities
            - Partnerships
            - Cost structures
            - Customer relationships
            - Market positioning

            Provide a concise summary of the relevant information found in this section.
            If you find information about any of these aspects, include it in your summary.
            """

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Here's part {
                        chunk_num} of {total_chunks} to analyze:\n\n{chunk}"}
                ],
                temperature=0.5,
                max_completion_tokens=10000
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"Error analyzing chunk {chunk_num}: {e}")
            return ""

    def analyze_business_model(self, content: str) -> Dict[str, Any]:
        """Analyze the business model using OpenAI's API"""
        try:
            # Split content into chunks
            chunks = self.chunk_content(content)
            print(f"Split content into {len(chunks)} chunks")

            # Analyze each chunk
            chunk_analyses = []
            for i, chunk in enumerate(chunks, 1):
                print(f"Analyzing chunk {i} of {len(chunks)}...")
                analysis = self.analyze_chunk(chunk, i, len(chunks))
                chunk_analyses.append(analysis)
                # Save intermediate results
                self.save_analysis('\n\n'.join(chunk_analyses),
                                   f"chunk_analysis_{i}.txt")

            # Combine chunk analyses
            combined_analysis = '\n\n'.join(chunk_analyses)

            # Save combined analyses for reference
            self.save_analysis(combined_analysis, "combined_analyses.txt")

            # Split combined analysis into smaller parts for final synthesis
            combined_chunks = self.chunk_content(
                combined_analysis, max_tokens=200000)
            print(f"Split combined analysis into {
                  len(combined_chunks)} parts for final synthesis")

            final_analyses = []
            for i, chunk in enumerate(combined_chunks, 1):
                try:
                    print(f"Synthesizing part {i} of {
                          len(combined_chunks)}...")
                    system_message = f"""
                    You are a business analyst expert synthesizing part {i} of {len(combined_chunks)} of the analysis.
                    Focus on these aspects for this section:

                    Part 1 (Sections 1-5):
                    - Value Proposition
                    - Customer Segments
                    - Revenue Streams
                    - Key Resources
                    - Key Activities

                    Part 2 (Sections 6-10):
                    - Key Partners
                    - Cost Structure
                    - Customer Relationships
                    - Channels
                    - Competitive Advantages

                    Part 3 (Sections 11-14):
                    - Market Position
                    - Growth Strategy
                    - Risks and Challenges
                    - Recommendations

                    Analyze the information provided and structure your response according to the relevant sections for this part.
                    Provide detailed insights based on the available information.
                    If certain information is not available, make reasonable assumptions and note them.
                    """

                    response = self.client.chat.completions.create(
                        model="gpt-4o-2024-08-06",
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": f"Here's part {i} of {
                                len(combined_chunks)} to synthesize:\n\n{chunk}"}
                        ],
                        temperature=0.7,
                        max_tokens=2000
                    )

                    final_analyses.append(response.choices[0].message.content)
                    # Save intermediate synthesis results
                    self.save_analysis('\n\n'.join(
                        final_analyses), f"final_synthesis_{i}.txt")

                except Exception as e:
                    print(f"Error in final synthesis part {i}: {e}")
                    return {}

            # Combine all final analyses
            final_analysis = '\n\n'.join(final_analyses)

            # Save raw analysis
            self.save_analysis(final_analysis, "raw_analysis.txt")

            try:
                # Process and structure the analysis
                structured_analysis = self.structure_analysis(final_analysis)
                print("Successfully structured the analysis")
                return structured_analysis
            except Exception as e:
                print(f"Error structuring final analysis: {e}")
                return {}

        except Exception as e:
            print(f"Error in analysis: {e}")
            return {}

    def structure_analysis(self, raw_analysis: str) -> Dict[str, Any]:
        """Convert the raw analysis into a structured format"""
        sections = [
            "Value Proposition", "Customer Segments", "Revenue Streams",
            "Key Resources", "Key Activities", "Key Partners",
            "Cost Structure", "Customer Relationships", "Channels",
            "Competitive Advantages", "Market Position", "Growth Strategy",
            "Risks and Challenges", "Recommendations"
        ]

        # Initialize structured data with empty content
        structured_data = {section: [] for section in sections}
        current_section = None

        # Split content into lines and process each line
        lines = raw_analysis.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Remove markdown formatting
            line = line.replace('#', '').strip()
            if line.startswith('###'):
                line = line[3:].strip()

            # Check for section headers
            found_section = None
            for section in sections:
                # Various header formats
                patterns = [
                    f"{section}",
                    f"{section}:",
                    f"{len(structured_data)+1}. {section}",
                    f"{len(structured_data)+1}. {section}:"
                ]
                if any(line.lower().startswith(pattern.lower()) for pattern in patterns):
                    found_section = section
                    break

            if found_section:
                current_section = found_section
                i += 1
                # Collect content until next section or end
                while i < len(lines):
                    content_line = lines[i].strip()
                    if not content_line:
                        i += 1
                        continue

                    # Check if this line starts a new section
                    is_new_section = False
                    for section in sections:
                        if any(content_line.lower().startswith(pattern.lower()) for pattern in [
                            f"### {section}",
                            f"{section}",
                            f"{section}:",
                            f"{len(structured_data)+1}. {section}",
                            f"{len(structured_data)+1}. {section}:"
                        ]):
                            is_new_section = True
                            break

                    if is_new_section:
                        break

                    structured_data[current_section].append(content_line)
                    i += 1
            else:
                i += 1

        # Join content for each section and handle empty sections
        for section in sections:
            if structured_data[section]:
                structured_data[section] = '\n'.join(structured_data[section])
            else:
                structured_data[section] = "Information not available"

        return structured_data

    def save_analysis(self, content: str | Dict[str, Any], filename: str) -> None:
        """Save the analysis to a file"""
        try:
            file_path = self.output_dir / filename
            if isinstance(content, dict):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            print(f"Analysis saved to {file_path}")
        except Exception as e:
            print(f"Error saving analysis: {e}")

    def run(self) -> None:
        """Run the complete analysis process"""
        print("Starting business model analysis...")

        # Read content
        content = self.read_content()
        if not content:
            print("No content to analyze")
            return

        # Analyze content
        analysis = self.analyze_business_model(content)
        if not analysis:
            print("Analysis failed")
            return

        # Save structured analysis
        self.save_analysis(analysis, "structured_analysis.json")
        print("Analysis complete!")


if __name__ == "__main__":
    analyzer = BusinessModelAnalyzer()
    analyzer.run()
