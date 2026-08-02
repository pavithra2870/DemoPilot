# BUILD PROJECT: DemoPilot — AI Sales Engineer for Asynchronous B2B Product Demos

You are a senior full-stack AI engineer, AI systems architect, and product engineer.

Your task is to build a complete, working MVP called **DemoPilot**.

Do not create a simple chatbot.

The product is an **AI Sales Engineer** that allows B2B SaaS founders and solopreneurs to create an asynchronous, interactive product demo that can guide prospects through their product, answer questions, handle objections, personalize the walkthrough, and qualify leads without requiring the founder to attend a live sales call.

The project must be built using free-tier-friendly technologies and must be practical to run locally.

---

# 1. CORE PRODUCT GOAL

Solve this problem:

B2B solopreneurs and technical founders often cannot attend discovery calls and product demos because they work full-time jobs, operate across time zones, or have limited sales capacity.

Prospects who want to understand the product may:

* Visit the website outside business hours
* Have questions about the product
* Need a personalized walkthrough
* Want to understand pricing and integrations
* Have technical objections
* Leave before booking a meeting

DemoPilot acts as an always-available AI Sales Engineer.

The product should:

1. Understand the prospect's business and use case.
2. Understand the founder's product using uploaded knowledge.
3. Guide the prospect through an interactive product demo.
4. Answer product, pricing, technical, and FAQ questions using RAG.
5. Personalize the demo based on prospect context.
6. Handle common objections.
7. Ask qualification questions naturally.
8. Calculate a lead score.
9. Generate a structured lead intelligence report for the founder.
10. Recommend whether the founder should follow up.

---

# 2. IMPORTANT PRODUCT POSITIONING

Do NOT build a generic AI chatbot.

The system must behave like an:

> AI Sales Engineer + Interactive Product Demonstrator + Lead Qualification Agent

The key differentiator is that the AI should be able to control the demo experience.

For example:

Prospect:
"Show me how your analytics feature works."

The AI should be able to return a structured action such as:

{
"message": "Let me show you the analytics dashboard.",
"action": {
"type": "navigate",
"target": "analytics"
}
}

The frontend must execute the action and navigate the prospect to the relevant demo section.

The AI should be able to:

* Navigate between demo sections
* Highlight features
* Open relevant product screens
* Display contextual information
* Ask questions
* Adapt the walkthrough based on prospect responses

---

# 3. REQUIRED TECH STACK

## Frontend

* React
* Javascript
* Vite
* custom CSS
* React Router
* Zustand or another lightweight state management solution

## Backend

* Python
* FastAPI
* Pydantic
* WebSockets where appropriate

## AI

Use the GROQ API.

Do NOT use the Gemini API.

Use the Groq OpenAI-compatible API format.

The LLM provider must be abstracted behind a service layer so the model can be changed later.

Use a fast Groq-supported instruction-following model available through the configured API key.

The model name must be configurable through environment variables.

Example:

GROQ_API_KEY=your_key
GROQ_MODEL=your_model

Never hardcode API keys.

## Embeddings

Use a free/local embedding solution.

Preferred:

* sentence-transformers
* all-MiniLM-L6-v2

Do not use a paid embedding API.

## Vector Search

Use:

* FAISS for local development

The RAG system must support:

* Document ingestion
* Text extraction
* Chunking
* Embedding generation
* Vector indexing
* Similarity search
* Context retrieval

## Database

Use:

* Supabase 

The system should be compatible with the Supabase free tier.

Use Supabase for:

* Founder accounts
* Product profiles
* Uploaded document metadata
* Prospects
* Conversations
* Lead scores
* Qualification answers
* Demo analytics

Keep the database schema simple and free-tier-friendly.

## Authentication

Use Supabase Auth if authentication is required.

Implement a clean architecture so authentication can be expanded later.

## Deployment

Design the project so it can be deployed using free-tier services such as:

* Render for frontend
* Huggingface spaces free tier for backend
* Supabase for database

The application must also run locally.

---

# 4. PRODUCT USER TYPES

There are two primary user types.

## A. Founder / Admin

The founder:

1. Creates an account.
2. Creates a product profile.
3. Enters product information.
4. Uploads documentation.
5. Adds FAQs.
6. Adds pricing information.
7. Adds integrations.
8. Adds common objections and responses.
9. Configures the ideal customer profile.
10. Creates a demo workspace.
11. Views prospects and lead intelligence.

## B. Prospect

The prospect:

1. Opens a public demo link.
2. Provides basic context about themselves.
3. Interacts with the AI Sales Engineer.
4. Receives a personalized product walkthrough.
5. Asks questions.
6. Explores product features.
7. Receives answers grounded in the founder's knowledge base.
8. Completes qualification questions naturally.
9. Optionally submits contact information.
10. Gets a clear next step such as:

* Book a call
* Request access
* Contact the founder
* Start a trial

---

# 5. FOUNDER INPUTS

The founder should be able to provide:

## Product Information

* Product name
* Product description
* Product category
* Target customers
* Main problem solved
* Main benefits
* Pricing
* Features
* Integrations
* Security information
* FAQs
* Common objections
* Case studies

## Ideal Customer Profile

* Industry
* Company size
* Job title
* Typical pain points
* Budget range
* Buying timeline
* Current alternatives
* Qualification criteria

## Demo Configuration

Create demo sections such as:

* Overview
* Problem
* Main Feature
* Workflow
* Analytics
* Integrations
* Pricing
* FAQ
* Call to Action

Each section should have:

* Section ID
* Title
* Description
* Screenshot or visual placeholder
* Feature explanation
* Relevant keywords

Example:

{
"id": "analytics",
"title": "Analytics Dashboard",
"description": "Monitor performance and identify trends.",
"keywords": ["analytics", "reports", "metrics", "dashboard"]
}

---

# 6. PROSPECT INPUTS

The prospect should be able to provide:

* Name
* Email
* Company
* Job title
* Industry
* Company size
* Main problem
* Current solution
* Timeline
* Budget range

Do not force the prospect to answer every question at the beginning.

The AI should collect information conversationally.

The conversation should feel natural.

---

# 7. AI SALES ENGINEER BEHAVIOR

The AI should follow this general flow.

## Stage 1: Welcome

Example:

"Welcome! I can walk you through the product based on what your team is trying to solve. What brings you here today?"

## Stage 2: Discover

The AI identifies:

* Who the prospect is
* What company they represent
* What problem they have
* What solution they currently use
* What they are trying to achieve

## Stage 3: Personalize

The AI determines which demo sections are most relevant.

Example:

If the prospect says:

"We are a 50-person SaaS company struggling with customer support."

The AI should prioritize:

1. Support workflow
2. Automation
3. Analytics
4. Integrations
5. Pricing

It should not force the prospect through irrelevant sections.

## Stage 4: Demonstrate

The AI explains the relevant feature and controls the frontend demo.

## Stage 5: Answer Questions

Use RAG to answer questions based on:

* Product documentation
* FAQs
* Pricing
* Technical documentation
* Case studies

Never invent product capabilities.

If the answer is unavailable, clearly say:

"I don't have enough information to confirm that."

## Stage 6: Handle Objections

Common objections:

* Too expensive
* We already use another tool
* Switching is difficult
* Is this secure?
* Does this integrate with our system?
* We need to think about it
* We can build this internally

The AI should respond using the founder's configured objection-handling knowledge.

## Stage 7: Qualify

The AI should naturally identify:

* Problem severity
* Urgency
* Budget
* Company fit
* Decision-making authority
* Current solution
* Buying timeline

Do not repeatedly interrogate the prospect.

The questions should be conversational.

## Stage 8: Conversion

At the end, the AI should recommend a relevant next step:

* Book a demo
* Request a trial
* Contact the founder
* Join a waitlist
* Request pricing

---

# 8. AI OUTPUT FORMAT

The LLM must return structured JSON whenever possible.

Use Pydantic models to validate the response.

Example:

{
"message": "Based on what you described, the analytics workflow is probably the most relevant place to start.",
"intent": "request_demo_section",
"action": {
"type": "navigate",
"target": "analytics"
},
"qualification": {
"company_size": null,
"industry": "SaaS",
"pain_point": "customer support overload",
"budget": null,
"timeline": null
},
"lead_score": 62,
"next_question": "How is your team currently handling this workflow?"
}

Supported action types should include:

* navigate
* highlight
* open_pricing
* show_faq
* show_integration
* request_contact
* end_demo
* none

The frontend must safely validate and execute actions.

Never allow arbitrary code execution from LLM output.

---

# 9. RAG SYSTEM

Build a real RAG pipeline.

Pipeline:

1. Founder uploads document.
2. Backend extracts text.
3. Text is cleaned.
4. Text is split into chunks.
5. Chunks receive metadata.
6. Local embedding model generates vectors.
7. Vectors are stored in FAISS.
8. User asks a question.
9. Query is embedded.
10. Relevant chunks are retrieved.
11. Retrieved context is passed to Groq.
12. Groq generates a grounded answer.

The RAG system must include source metadata.

The AI should know which document or section was used to answer.

Prevent hallucinations using:

* Strict system instructions
* Retrieved context
* Confidence handling
* "I don't know" behavior
* Source-aware responses

---

# 10. LEAD SCORING

Create a transparent lead scoring system.

Example:

Problem Fit: 0–25
Urgency: 0–20
Budget Fit: 0–20
Company Fit: 0–20
Buying Timeline: 0–15

Total:

0–39 = Low Intent
40–69 = Medium Intent
70–100 = High Intent

The score must be explainable.

Do not only output:

"Lead score: 87"

Also output:

{
"score": 87,
"classification": "High Intent",
"reasons": [
"Strong problem fit",
"Buying timeline within 30 days",
"Budget matches product pricing",
"Company fits the target customer profile"
]
}

---

# 11. FOUNDER DASHBOARD

Build a clean dashboard with:

## Overview

* Total prospects
* Total demo sessions
* Qualified leads
* High-intent leads
* Conversion rate

## Lead List

Each lead should show:

* Name
* Company
* Industry
* Lead score
* Intent classification
* Main pain point
* Last activity
* Recommended action

## Lead Detail Page

Show:

* Full conversation
* Qualification answers
* Lead score breakdown
* Questions asked
* Features viewed
* Demo sections visited
* AI-generated summary
* Recommended founder follow-up

Example:

"XYZ is a 50-person SaaS company experiencing support ticket overload. They currently use Zendesk. They showed strong interest in automation and analytics. Their estimated timeline is within 30 days. Recommended action: follow up with a personalized integration demo."

---

# 12. ANALYTICS

Track:

* Demo sessions
* Session duration
* Most visited demo sections
* Most frequently asked questions
* Common objections
* Conversion to contact request
* Lead score distribution

This data should help the founder understand what prospects care about.

---

# 13. SECURITY REQUIREMENTS

Implement:

* Environment variables
* No API keys in frontend
* Backend-only Groq API calls
* Input validation
* Pydantic validation
* Rate limiting where practical
* Safe JSON parsing
* No arbitrary code execution
* File upload validation
* Basic prompt injection protection for uploaded documents

Treat uploaded documents as untrusted content.

The product knowledge base must not be allowed to override the system's core instructions.

---

# 14. PROJECT ARCHITECTURE

Use a clean structure similar to:

frontend/

src/
components/
pages/
layouts/
hooks/
services/
store/
types/

backend/

app/
main.py
api/
core/
models/
schemas/
services/
groq_service.py
rag_service.py
demo_service.py
qualification_service.py
lead_scoring_service.py
ai_services/
**init**.py
llm/
agents/
prompts/
structured_outputs/
memory/
agents/
sales_engineer_agent.py
qualification_agent.py
database/
utils/

rag/

ingestion/
embeddings/
vector_store/

The `ai_services/` folder must contain AI-specific orchestration and reusable AI capabilities, while the regular `services/` folder should contain application/business logic.

Do not put all logic into one file.

---

# 15. BUILD STRATEGY

Build in phases.

## Phase 1: Foundation

* Project setup
* Frontend
* Backend
* Database
* Environment configuration
* Basic API connection

## Phase 2: Product Knowledge

* Product profile
* Document upload
* Text extraction
* Chunking
* Embeddings
* FAISS search

## Phase 3: AI Sales Engineer

* Groq integration
* Structured output
* RAG-powered answers
* Conversation memory
* Intent detection

## Phase 4: Interactive Demo

* Demo sections
* AI navigation actions
* Feature highlighting
* Product walkthrough

## Phase 5: Qualification

* Qualification state
* Lead scoring
* Lead classification
* Explainable scoring

## Phase 6: Founder Dashboard

* Lead list
* Lead details
* Conversation history
* Analytics

## Phase 7: Polish

* Error handling
* Loading states
* Empty states
* Responsive UI
* Security
* Documentation

ensure that every phase builds correctly and works correctly
---

# 16. IMPORTANT DEVELOPMENT RULES

1. Do not overengineer the MVP.
2. Do not use paid APIs.
3. Do not use Gemini.
4. Use Groq as the primary LLM provider.
5. Use local embeddings.
6. Use FAISS for vector search.
7. Keep the architecture modular.
8. Use real working functionality instead of mock buttons.
9. Do not build a fake chatbot demo.
10. Do not hardcode product-specific information.
11. Make the system configurable for any B2B SaaS product.
12. Use structured LLM outputs.
13. Validate all LLM responses.
14. Implement proper error handling.
15. Keep API keys server-side.
16. Build the MVP incrementally.
17. Do not add unnecessary features before the core workflow works.

---

# 17. DEFINITION OF DONE

The project is complete when the following end-to-end workflow works:

Founder:

1. Creates a product profile.
2. Adds product information.
3. Uploads product documentation.
4. Configures ICP and qualification criteria.
5. Creates demo sections.

Prospect:

1. Opens a public demo link.
2. Starts a conversation with the AI Sales Engineer.
3. Describes their company and problem.
4. Receives a personalized demo.
5. AI navigates the demo interface.
6. Prospect asks questions.
7. AI answers using RAG.
8. Prospect raises objections.
9. AI handles the objections.
10. AI collects qualification information naturally.
11. AI calculates lead score.
12. Prospect submits contact information.

Founder:

1. Opens the dashboard.
2. Sees the new lead.
3. Views the conversation.
4. Views qualification answers.
5. Sees the lead score and explanation.
6. Sees the AI-generated follow-up recommendation.

This complete workflow must work before adding advanced features such as:

* AI avatars
* Video generation
* CRM integrations
* Calendar integrations
* Automated email follow-ups
* Multi-tenant enterprise architecture

---

# FIRST TASK

Before writing large amounts of code:

1. Analyze this specification.
2. Create the complete technical architecture.
3. Define the database schema.
4. Define the API endpoints.
5. Define the frontend routes.
6. Define the core Pydantic models.
7. Define the AI agent state machine.
8. Define the RAG pipeline.
9. Define the structured LLM output schemas.
10. Define the implementation plan.

Then begin implementing the project phase by phase.

Do not skip directly to a superficial chatbot.

The final product must feel like a real AI-powered asynchronous B2B sales engineer.

readme.md is for people who see my github repo
give a setup.md which guides me on how to set up the project in detailed way (like wat scripts to run on supabase sql editor, architetcure notes, product details)