import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="PortfolioPal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Schemas ---------
class ProjectInput(BaseModel):
    title: str
    description: str
    technologies: Optional[List[str]] = Field(default_factory=list)
    audience: Optional[str] = None
    tone: Optional[str] = "professional"


class PortfolioProject(BaseModel):
    name: str
    description: str
    highlights: Optional[List[str]] = Field(default_factory=list)
    tech: Optional[List[str]] = Field(default_factory=list)
    link: Optional[str] = None


class EducationItem(BaseModel):
    school: str
    degree: str
    period: Optional[str] = None
    details: Optional[str] = None


class PortfolioInput(BaseModel):
    name: str
    role: str
    summary: str
    projects: List[PortfolioProject] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    tone: Optional[str] = "confident"
    language: Optional[str] = "English"


# --------- Helpers ---------

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)
        return client
    except Exception:
        return None


def ai_generate(prompt: str) -> str:
    """Generate text using OpenAI if available, otherwise fallback to a smart template."""
    client = get_openai_client()
    if client:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are PortfolioPal, an expert portfolio and project description writer. Be concise, clear, and engaging."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""
        except Exception:
            pass

    # Fallback template if no API key or error
    return (
        "[AI Fallback] "
        + "\n".join([
            "Thanks for trying PortfolioPal!",
            "This is a locally generated sample response because no AI key was detected.",
            "Add OPENAI_API_KEY to enable real AI results.",
            "\n---\n",
            prompt[:1000],
        ])
    )


# --------- Routes ---------
@app.get("/")
def read_root():
    return {"message": "PortfolioPal API is running."}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from PortfolioPal backend!"}


@app.post("/api/ai/project-writer")
def generate_project_writer(body: ProjectInput):
    prompt = (
        f"Write a compelling, structured project description.\n"
        f"Title: {body.title}\n"
        f"Audience: {body.audience or 'Hiring managers and peers'}\n"
        f"Tone: {body.tone}\n"
        f"Technologies: {', '.join(body.technologies) if body.technologies else 'N/A'}\n"
        f"Base description: {body.description}\n\n"
        "Output format: \n"
        "- One-sentence hook\n- Problem & Motivation\n- Approach & Architecture\n- Key Features (bullet list)\n- Tech Stack\n- Impact & Results\n- What I learned\n"
    )
    text = ai_generate(prompt)
    return {"result": text}


@app.post("/api/ai/portfolio")
def generate_portfolio(body: PortfolioInput):
    projects_text = "\n".join(
        [
            f"Project: {p.name}\nDesc: {p.description}\nHighlights: {', '.join(p.highlights or [])}\nTech: {', '.join(p.tech or [])}\nLink: {p.link or 'N/A'}"
            for p in body.projects
        ]
    )
    education_text = "\n".join(
        [
            f"Education: {e.school} — {e.degree} ({e.period or 'period N/A'})\nDetails: {e.details or ''}"
            for e in body.education
        ]
    )
    skills_text = ", ".join(body.skills)

    prompt = (
        f"Create a polished, responsive-ready portfolio content in {body.language}.\n"
        f"Name: {body.name}\nRole: {body.role}\nSummary: {body.summary}\n"
        f"Desired tone: {body.tone}\n\n"
        f"Projects:\n{projects_text}\n\n"
        f"Education:\n{education_text}\n\n"
        f"Skills: {skills_text}\n\n"
        "Output as JSON with keys: hero, about, projects (array with name, blurb, bullets, tech, link), education (array), skills (array), cta. Keep each text concise."
    )
    text = ai_generate(prompt)
    return {"result": text}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Used",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    # Check environment variables for DB presence
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
