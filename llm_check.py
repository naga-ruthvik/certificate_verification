from google import genai
from openai import OpenAI
from pprint import pprint
import json
import requests
from scraping import get_dynamic_website_text

url_text="https://coursera.org/verify/NJZWGZG8MJ6T"
pdf_data="""Mar 17,  2024
Anvesh
Crash Course on Python
an online non-credit course authorized by Google and offered through Coursera
has successfully completed
Google
Verify at:
https://coursera.org/verify/NJZWGZG8MJ6T
  Cour ser a has confir med the identity of this individual and their
par ticipation in the cour se."""

# This is the prompt string you would pass to the API
prompt = f"""
You are a web extraction bot. Your ONLY job is to visit the single URL below and extract data.

**Primary Directive:**
- You MUST access this URL: `{url_text}`
- You are STRICTLY FORBIDDEN from accessing any other URL or performing any web searches.

**Failure Condition:**
- If the URL is inaccessible or you cannot extract the data, DO NOT search for alternatives. Your ONLY action is to report the failure in the JSON output as specified below.

**Task:**
1. Visit the URL.
2. Extract the student's name, course name, and completion date.
3. Compare the extracted details against this reference data: ```json\n{json.dumps(pdf_data)}\n```
4. Respond with ONLY the JSON object below. Your response MUST start with `{{` and contain nothing else.

**Output Format:**
```json
{{
  "is_verified": <boolean>,
  "reasoning": "<Explain failure if URL was inaccessible, or explain the data mismatch.>",
  "extracted_url_data": {{
    "student_name": "<name from URL or null>",
    "course_name": "<course from URL or null>",
    "completion_date": "<date from URL or null>"
  }}
}}

"""


# def analyze_url_gemini(url):
#     url_text=get_dynamic_website_text(url)
#     prompt = f"""
#         You are an expert certificate verification agent. Your task is to verify if the information on a provided webpage confirms the details of a given certificate.

#         **Certificate Data (from PDF):**
#         {json.dumps(pdf_data, indent=2)}

#         **Webpage Content (from URL):**
#         "{url_text}"

#         **Your Task:**
#         1. Carefully read the "Webpage Content".
#         2. Find the student's name, course name, and completion date within it.
#         3. Compare this information with the "Certificate Data". Account for minor variations (e.g., middle initials, date formats).
#         4. Based on your comparison, determine if the certificate is verified.
#         5. Respond with ONLY a valid JSON object containing your findings. Do not add any text before or after the JSON.

#         **JSON Output Format:**
#         {{
#           "is_verified": boolean,
#           "confidence_score": number (from 0.0 for no match to 1.0 for a perfect match),
#           "reasoning": "A brief explanation of your decision.",
#           "extracted_url_data": {{
#             "student_name": "The name found on the webpage",
#             "course_name": "The course found on the webpage",
#             "completion_date": "The date found on the webpage"
#           }}
#         }}
#         """
#     client = genai.Client(api_key="AIzaSyAYSg8fomuImTapCNLL40AnU1UMtLXe4kg")
#     generation_config = {"response_mime_type": "application/json"}
#     response=client.models.generate_content(
#         model='gemini-2.5-flash',
#         contents=prompt,
#         config=generation_config
#     )

#     return response.text

# def analyze_url_openai(prompt:str):
#     client=OpenAI(
#         base_url="https://openrouter.ai/api/v1",
#         api_key="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")
#     try:
#         # 1. Correct method is client.chat.completions.create
#         completion = client.chat.completions.create(
#             # 2. Use a real, available model identifier
#             model="openai/gpt-4o",  # Example: Using GPT-4o
#             # 3. The 'messages' parameter is required, with a specific list/dict structure
#             messages=[
#                 {
#                     "role": "user",
#                     "content": prompt,
#                 },
#             ],
#         )
#         # The actual text response is in choices[0].message.content
#         return completion.choices[0].message.content
    
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         return None

def analyze_url_perplexity(prompt):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": "Bearer ",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,               
        "max_tokens": 1000,              
        "stream": False      
    }
    response = requests.post(url, headers=headers, json=payload)
    # api_data = response.json()
  
    # content_string = api_data['choices'][0]['message']['content']
    # final_data = json.loads(content_string)
    # return final_data
    return response.text

pprint(analyze_url_perplexity(prompt))

def page_content(url):
    response=requests.get(url)
    print(response.text)

# page_content(url_text)