# EU-Legal-Documents-Converter
Converts HTML files from EUR LEX to JSON files.
When working with Legal Documents / Regulations from https://eur-lex.europa.eu/ a lot of people face the issue that those documents are hard for AI to understand.
The internal OCR parsers of tools like ChatGPT or Gemini often parse only the first 50,60 or 70 pages and hallucinate the rest.

Therefore I used Gemini3 to create a script to solve this problem.
It will generate two JSON files:
1.) Human readable JSON
2.) Optimized for RAG training /LLMs 

# How it works:
1. Go to https://eur-lex.europa.eu/ download your intended laws, like AI Act, CRA as HTML file
2. Place them into the working folder
3. Run the Python script

I will give no garantuee for corretness, so do your own cross checks
