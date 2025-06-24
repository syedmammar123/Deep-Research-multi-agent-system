%pip install llama-index
%pip install tavily-python
%pip install llama-index-llms-groq

from llama_index.llms.openai import OpenAI
from llama_index.llms.groq import Groq

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.workflow import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.core.workflow import Context
from tavily import AsyncTavilyClient
from llama_index.core.workflow import Event

import os
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.getenv("openai_api_key")
tvly_api_key = os.getenv("tvly_api_key")
print(openai_api_key)
print(tvly_api_key)

llm = OpenAI(model="gpt-4.1-mini", api_key=openai_api_key)

response = llm.complete("What's capital of Sindh?")

response.text

async def search_web(query: str) -> str:
    """Useful for using the web to answer questions."""
    client = AsyncTavilyClient(api_key=tvly_api_key)
    return str(await client.search(query))

question_agent = FunctionAgent(
    tools=[],
    llm=llm,
    verbose=False,
    system_prompt="""You are part of a deep research system.
      Given a research topic, you should come up with a bunch of questions
      that a separate agent will answer in order to write a comprehensive
      report on that topic. To make it easy to answer the questions separately,
      you should provide the questions one per line. Don't include markdown
      or any preamble in your response, just a list of questions."""
)
answer_agent = FunctionAgent(
    tools=[search_web],
    llm=llm,
    verbose=False,
    system_prompt="""You are part of a deep research system.
      Given a specific question, your job is to come up with a deep answer
      to that question, which will be combined with other answers on the topic
      into a comprehensive report. You can search the web to get information
      on the topic, as many times as you need."""
)
report_agent = FunctionAgent(
    tools=[],
    llm=llm,
    verbose=False,
    system_prompt="""You are part of a deep research system.
      Given a set of answers to a set of questions, your job is to combine
      them all into a comprehensive report on the topic."""
)

class GenerateEvent(Event):
  research_topic: str

class QuestionEvent(Event):
    question: str

class AnswerEvent(Event):
    question: str
    answer: str

class ProgressEvent(Event):
    msg: str

class DeepResearchWorkflow(Workflow):

    @step
    async def setup(self, ctx: Context, ev: StartEvent) -> GenerateEvent:
        self.question_agent = ev.question_agent
        self.answer_agent = ev.answer_agent
        self.report_agent = ev.report_agent

        ctx.write_event_to_stream(ProgressEvent(msg="Starting research"))

        return GenerateEvent(research_topic=ev.research_topic)

    @step
    async def generate_questions(self, ctx: Context, ev: GenerateEvent) -> QuestionEvent:

        await ctx.set("research_topic", ev.research_topic)
        ctx.write_event_to_stream(ProgressEvent(msg=f"Research topic is {ev.research_topic}"))

        result = await self.question_agent.run(user_msg=f"""Generate some questions
          on the topic <topic>{ev.research_topic}</topic>.""")

        # some basic string manipulation to get separate questions
        lines = str(result).split("\n")
        questions = [line.strip() for line in lines if line.strip() != ""]

        # record how many answers we're going to need to wait for
        await ctx.set("total_questions", len(questions))

        # fire off multiple Answer Agents
        for question in questions:
            ctx.send_event(QuestionEvent(question=question))

    @step
    async def answer_question(self, ctx: Context, ev: QuestionEvent) -> AnswerEvent:

        result = await self.answer_agent.run(user_msg=f"""Research the answer to this
          question: <question>{ev.question}</question>. You can use web
          search to help you find information on the topic, as many times
          as you need. Return just the answer without preamble or markdown.""")

        ctx.write_event_to_stream(ProgressEvent(msg=f"""Received question {ev.question}
            Came up with answer: {str(result)}"""))

        return AnswerEvent(question=ev.question,answer=str(result))

    @step
    async def write_report(self, ctx: Context, ev: AnswerEvent) -> StopEvent:

        research = ctx.collect_events(ev, [AnswerEvent] * await ctx.get("total_questions"))
        # if we haven't received all the answers yet, this will be None
        if research is None:
            ctx.write_event_to_stream(ProgressEvent(msg="Collecting answers..."))
            return None

        ctx.write_event_to_stream(ProgressEvent(msg="Generating report..."))

        # aggregate the questions and answers
        all_answers = ""
        for q_and_a in research:
            all_answers += f"Question: {q_and_a.question}\nAnswer: {q_and_a.answer}\n\n"

        # prompt the report
        result = await self.report_agent.run(user_msg=f"""You are part of a deep research system.
          You have been given a complex topic on which to write a report:
          <topic>{await ctx.get("research_topic")}.

          Other agents have already come up with a list of questions about the
          topic and answers to those questions. Your job is to write a clear,
          thorough report that combines all the information from those answers.

          Here are the questions and answers:
          <questions_and_answers>{all_answers}</questions_and_answers>""")

        return StopEvent(result=str(result))


topic_of_research = "temperature of karachi on 24th june 2025"

workflow = DeepResearchWorkflow(timeout=300)

handler = workflow.run(
    research_topic=topic_of_research,
    question_agent=question_agent,
    answer_agent=answer_agent,
    report_agent=report_agent
)

async for ev in handler.stream_events():
    if isinstance(ev, ProgressEvent):
        print(ev.msg)

final_result = await handler
print("==== The report ====")
print(final_result)