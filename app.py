from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime

# Import your existing research system
from llama_index.llms.openai import OpenAI
from llama_index.llms.groq import Groq
from llama_index.core.agent.workflow import FunctionAgent
from tavily import TavilyClient

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Global variables to store API keys
groq_api_key = None
tvly_api_key = None

def search_web(query: str) -> str:
    """Useful for using the web to answer questions."""
    if not tvly_api_key:
        return "Tavily API key not configured"
    try:
        client = TavilyClient(api_key=tvly_api_key)
        result = client.search(query)
        return str(result)
    except Exception as e:
        return f"Search failed: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_api_keys', methods=['POST'])
def set_api_keys():
    global groq_api_key, tvly_api_key
    data = request.get_json()
    tvly_api_key = data.get('tvly_api_key')
    groq_api_key = data.get("groq_api_key")

    if not tvly_api_key or not groq_api_key:
        return jsonify({'success': False, 'message': 'Both API keys are required'})

    return jsonify({'success': True, 'message': 'API keys set successfully'})

@app.route('/start_research', methods=['POST'])
def start_research():
    data = request.get_json()
    topic = data.get('topic')

    if not groq_api_key or not tvly_api_key:
        return jsonify({'success': False, 'message': 'Please set your API keys first'})

    if not topic:
        return jsonify({'success': False, 'message': 'Please enter a research topic'})

    try:
        # Initialize LLM
        llm = Groq(model="openai/gpt-oss-20b", api_key=groq_api_key)

        progress_log = []

        # Step 1: Generate questions
        progress_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting research on: {topic}")

        question_prompt = f"""Generate 5-7 specific questions about this topic: {topic}
        Provide the questions one per line. Don't include markdown or any preamble, just a list of questions."""

        question_response = llm.complete(question_prompt)
        questions_text = question_response.text
        questions = [q.strip() for q in questions_text.split('\n') if q.strip()]

        progress_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Generated {len(questions)} questions")

        # Step 2: Answer each question
        all_answers = []
        for i, question in enumerate(questions, 1):
            progress_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Researching question {i}/{len(questions)}: {question[:50]}...")

            # Search the web for this question
            search_result = search_web(question)

            # Generate answer using the search result
            answer_prompt = f"""Based on this web search result, answer this question: {question}
            
            Web search result: {search_result}
            
            Provide a comprehensive answer based on the search results."""

            answer_response = llm.complete(answer_prompt)
            answer = answer_response.text

            all_answers.append(f"**Question {i}:** {question}\n\n**Answer:** {answer}\n\n---\n")
            progress_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Completed research for question {i}")

        # Step 3: Generate final report
        progress_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Generating comprehensive report...")

        report_prompt = f"""You are writing a comprehensive research report on: {topic}

        Here are the questions and answers that were researched:
        
        {''.join(all_answers)}
        
        Please write a clear, thorough report that combines all this information into a comprehensive analysis of the topic. 
        Structure it well with clear sections using markdown formatting:
        
        - Use # for main title
        - Use ## for section headers
        - Use ### for subsection headers
        - Use bullet points for lists
        - Use **bold** for emphasis
        - Use blockquotes for important quotes
        - Structure it with Executive Summary, Key Findings, Detailed Analysis, and Conclusion sections
        
        Make it professional and well-formatted for easy reading."""

        report_response = llm.complete(report_prompt)
        final_report = report_response.text

        # Ensure it starts with a proper title
        if not final_report.startswith('#'):
            final_report = f"# Research Report: {topic}\n\n{final_report}"

        progress_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Research completed successfully!")

        return jsonify({
            'success': True,
            'result': final_report,
            'progress': progress_log,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Research failed: {str(e)}'})


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "alive",
            "timestamp": datetime.now().isoformat(),
            "message": "Server is running!",
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
