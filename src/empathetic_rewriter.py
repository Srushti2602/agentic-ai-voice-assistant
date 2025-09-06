from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOllama


def ollama_chat(model: str = "mistral"):
    """Create a chat model using Ollama."""
    return ChatOllama(
        model=model,
        temperature=0.7,
        top_k=10,
        top_p=0.95,
        repeat_penalty=1.1,
    )


REWRITE_TMPL = ChatPromptTemplate.from_messages([
    ("system", """
You rewrite intake questions with a warm, calm, and empathetic tone.
Show understanding and compassion in your wording.
Soften questions to sound supportive and reassuring while keeping the meaning.
Ask exactly one clear, gentle question.
Keep placeholders like {name} untouched.
Use short sentences. Use simple, kind words.
No emojis. No em dash.
Return only the rewritten text.

Example:
Original: What injuries did you sustain?
Rewritten: I'm sorry to hear that. Could you please tell me about any injuries you experienced?
"""),
    ("user", "Original: {text}\nRewritten:")
])


GREETING_TMPL = ChatPromptTemplate.from_messages([
    ("system", """Write a short greeting for a legal intake agent.
Warm and clear. Two sentences max.
No emojis. No em dash."""),
    ("user", "Agent name: {agent}\nFirm: {firm}\nGreeting:")
])


class EmpatheticRewriter:
    def __init__(self):
        self.llm = ollama_chat()
        self.rewrite_chain = REWRITE_TMPL | self.llm | StrOutputParser()
        self.greet_chain = GREETING_TMPL | self.llm | StrOutputParser()
        self.cache = {}

    async def rewrite(self, text: str) -> str:
        if not text:
            return ""
        if text in self.cache:
            return self.cache[text]
        try:
            out = await self.rewrite_chain.ainvoke({"text": text})
            out = out.strip() or text
        except Exception:
            out = text
        self.cache[text] = out
        return out

    async def greeting(self, agent: str, firm: str) -> str:
        key = f"greet::{agent}::{firm}"
        if key in self.cache:
            return self.cache[key]
        try:
            out = await self.greet_chain.ainvoke({"agent": agent, "firm": firm})
            out = out.strip()
        except Exception:
            out = f"Thank you for calling {firm}. My name is {agent}. I will collect a few details to help you."
        self.cache[key] = out
        return out
