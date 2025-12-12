import json
from bs4 import BeautifulSoup
import os
import re

def parse_html_to_json(html_file_path, output_json_path):
    if not os.path.exists(html_file_path):
        print(f"Error: File not found at {html_file_path}")
        return

    with open(html_file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    data = {}

    # Extract Title
    title_div = soup.find('div', class_='eli-main-title')
    if title_div:
        title_parts = [p.get_text(strip=True) for p in title_div.find_all('p', class_='oj-doc-ti')]
        data['title'] = " ".join(title_parts)
    else:
        data['title'] = "Title not found"

    # Extract Recitals
    recitals = []
    recital_divs = soup.find_all('div', class_='eli-subdivision', id=lambda x: x and x.startswith('rct_'))

    for div in recital_divs:
        paragraphs = div.find_all('p', class_='oj-normal')
        if len(paragraphs) >= 2:
            recital_id = paragraphs[0].get_text(strip=True)
            recital_text = " ".join([p.get_text(strip=True) for p in paragraphs[1:]])
            recitals.append({
                "id": recital_id,
                "text": recital_text
            })
        elif len(paragraphs) == 1:
             recitals.append({
                "id": "",
                "text": paragraphs[0].get_text(strip=True)
            })

    data['recitals'] = recitals
    
    # Extract Chapters, Sections, Articles
    chapters = []
    
    # Find the container for the enacting terms, usually starts after "HAVE ADOPTED THIS REGULATION"
    # In the file, it seems to be followed by div id="enc_1" or similar structure.
    # We can look for all divs with id starting with "cpt_" that are NOT sections (no ".sct_" in id)
    
    chapter_divs = soup.find_all('div', id=lambda x: x and x.startswith('cpt_') and '.sct_' not in x)
    
    for cpt_div in chapter_divs:
        chapter_data = {
            "id": "",
            "title": "",
            "children": [] # Can be Sections or Articles
        }
        
        # Chapter Number
        cpt_num_p = cpt_div.find('p', class_='oj-ti-section-1')
        if cpt_num_p:
            chapter_data['id'] = cpt_num_p.get_text(strip=True)
            
        # Chapter Title
        cpt_tit_div = cpt_div.find('div', class_='eli-title')
        if cpt_tit_div:
            chapter_data['title'] = cpt_tit_div.get_text(strip=True)
        
        # Let's iterate through all direct children divs
        for child in cpt_div.find_all('div', recursive=False):
            child_id = child.get('id', '')
            
            # Case 1: Section
            if child_id.startswith(f"{cpt_div['id']}.sct_"):
                section_data = {
                    "type": "section",
                    "id": "",
                    "title": "",
                    "articles": []
                }
                
                # Section Number
                sct_num_p = child.find('p', class_='oj-ti-section-1')
                if sct_num_p:
                    section_data['id'] = sct_num_p.get_text(strip=True)
                
                # Section Title
                sct_tit_div = child.find('div', class_='eli-title')
                if sct_tit_div:
                    section_data['title'] = sct_tit_div.get_text(strip=True)
                    
                # Find Articles in Section
                # Articles in sections seem to be direct children of the section div
                for art_div in child.find_all('div', class_='eli-subdivision', recursive=False):
                    if art_div.get('id', '').startswith('art_'):
                        article_data = parse_article(art_div)
                        if article_data:
                            section_data['articles'].append(article_data)
                            # Check for stop condition
                            if "113" in article_data['id']: # Simple check, might need refinement
                                pass # We don't stop here, we just parsed it. 
                                # But if we want to STOP parsing completely after 113:
                                # We need a global flag or check.
                
                if section_data['id'] or section_data['title'] or section_data['articles']:
                    chapter_data['children'].append(section_data)
                
            # Case 2: Article (Directly in Chapter)
            elif child_id.startswith('art_'):
                article_data = parse_article(child)
                if article_data:
                    chapter_data['children'].append(article_data)
        
        if chapter_data['id'] or chapter_data['title'] or chapter_data['children']:
            chapters.append(chapter_data)
        
        # Let's check if we reached Article 113 in this chapter
        found_end = False
        for child in chapter_data['children']:
            if child.get('type') == 'article' and '113' in child.get('id', ''):
                found_end = True
            elif child.get('type') == 'section':
                for art in child.get('articles', []):
                    if '113' in art.get('id', ''):
                        found_end = True
        
        if found_end:
            break

    data['chapters'] = chapters
    data['signatories'] = parse_signatories(soup)
    data['footnotes'] = parse_footnotes(soup)
    data['annexes'] = parse_annexes(soup)

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Successfully converted {html_file_path} to {output_json_path}")
    print(f"Extracted {len(chapters)} chapters.")

def parse_signatories(soup):
    signatories = []
    signatory_divs = soup.find_all('div', class_='oj-signatory')
    
    for sig_div in signatory_divs:
        # Check if this div contains the relevant p tags
        p_tags = sig_div.find_all('p', class_='oj-signatory')
        if not p_tags:
            continue
            
        signatory_data = {
            "title": "",
            "name": ""
        }
        
        # Extract text from p tags
        texts = [p.get_text(strip=True) for p in p_tags]
        
        if len(texts) >= 2:
            # Heuristic: The last one is likely the name (all caps usually)
            signatory_data['name'] = texts[-1]
            signatory_data['title'] = " ".join(texts[:-1])
            signatories.append(signatory_data)
            
    return signatories

def parse_footnotes(soup):
    footnotes = []   
    note_ps = soup.find_all('p', class_='oj-note')
    
    for p in note_ps:
        # Extract ID
        id_span = p.find('span', class_='oj-super')
        if id_span:
            note_id = id_span.get_text(strip=True)
            
            # Extract text
            # The text is everything in the p tag.
            # We might want to clean up the "(1)" part from the text if we want just the content.
            # The structure is: <a>(<span>1</span>)</a>  Text...
            
            # Let's get the full text and remove the leading "(ID)"
            full_text = p.get_text(strip=True)
            
            # Expected start: "({note_id})"
            prefix = f"({note_id})"
            if full_text.startswith(prefix):
                text_content = full_text[len(prefix):].strip()
            else:
                text_content = full_text
                
            footnotes.append({
                "id": note_id,
                "text": text_content
            })
            
    return footnotes

def parse_annexes(soup):
    annexes = []
    # Annexes are in divs with id starting with 'anx_'
    # <div class="eli-container" id="anx_I">
    
    annex_divs = soup.find_all('div', id=lambda x: x and x.startswith('anx_'))
    
    for anx_div in annex_divs:
        annex_data = {
            "id": "",
            "title": "",
            "items": []
        }
        
        doc_ti_ps = anx_div.find_all('p', class_='oj-doc-ti')
        if len(doc_ti_ps) > 0:
            annex_data['id'] = doc_ti_ps[0].get_text(strip=True)
        if len(doc_ti_ps) > 1:
            annex_data['title'] = doc_ti_ps[1].get_text(strip=True)
            
        # Iterate through children to find content
        for child in anx_div.children:
            if child.name == 'p':
                if 'oj-doc-ti' in child.get('class', []):
                    continue # Already handled
                
                item_data = {}
                if 'oj-ti-grseq-1' in child.get('class', []):
                    item_data['type'] = 'section'
                    item_data['text'] = child.get_text(strip=True)
                elif 'oj-normal' in child.get('class', []):
                    item_data['type'] = 'paragraph'
                    item_data['text'] = child.get_text(strip=True)
                
                if item_data:
                    annex_data['items'].append(item_data)
                    
            elif child.name == 'table':
                # Tables usually contain list items
                rows = child.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    col_texts = [col.get_text(strip=True) for col in cols if col.get_text(strip=True)]
                    
                    if not col_texts:
                        continue
                        
                    item_data = {
                        "type": "item",
                        "id": "",
                        "text": ""
                    }
                    
                    if len(col_texts) == 1:
                        # Just text, or just a bullet?
                        # If it's a long text, it's the content.
                        # If it's short (like "1." or "-"), it might be an ID with empty text (unlikely).
                        item_data['text'] = col_texts[0]
                    elif len(col_texts) >= 2:
                        # First is ID, second is Text
                        item_data['id'] = col_texts[0]
                        item_data['text'] = " ".join(col_texts[1:])
                        
                    annex_data['items'].append(item_data)
                    
        annexes.append(annex_data)
    return annexes


def export_for_training(data, output_path):
    training_data = []
    
    # Process Recitals
    for recital in data.get('recitals', []):
        text_content = f"Recital {recital['id']}: {recital['text']}"
        training_data.append({
            "id": f"recital_{recital['id']}",
            "source": "AI Act",
            "type": "recital",
            "hierarchy": ["Recitals"],
            "text": text_content
        })
        
    # Process Chapters
    for chapter in data.get('chapters', []):
        chapter_context = f"Chapter {chapter['id']} - {chapter['title']}"
        
        for child in chapter.get('children', []):
            if child['type'] == 'section':
                section_context = f"{chapter_context} > Section {child['id']} - {child['title']}"
                for article in child.get('articles', []):
                    process_article(article, section_context, training_data)
            elif child['type'] == 'article':
                process_article(child, chapter_context, training_data)
                
    # Process Annexes
    for annex in data.get('annexes', []):
        annex_context = f"{annex['id']} - {annex['title']}"
        
        # Flatten annex items
        current_section = ""
        for item in annex.get('items', []):
            if item['type'] == 'section':
                current_section = item['text']
            elif item['type'] in ['item', 'paragraph']:
                hierarchy = [annex_context]
                if current_section:
                    hierarchy.append(current_section)
                
                text_content = f"{annex_context}"
                if current_section:
                    text_content += f" > {current_section}"
                
                if item.get('id'):
                     text_content += f" > Item {item['id']}: {item['text']}"
                else:
                     text_content += f" > {item['text']}"
                     
                training_data.append({
                    "id": f"annex_{annex['id']}_{len(training_data)}", # Simple unique ID
                    "source": "AI Act",
                    "type": "annex_item",
                    "hierarchy": hierarchy,
                    "text": text_content
                })

    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in training_data:
            json.dump(entry, f, ensure_ascii=False)
            f.write('\n')
            
    print(f"Successfully exported training data to {output_path}")
    print(f"Generated {len(training_data)} training chunks.")

def process_article(article, context, training_data):
    article_title = f"Article {article['id']} - {article['title']}"
    full_context = f"{context} > {article_title}"
    
    # Combine all content paragraphs into one text block for the article
    # Or split by paragraph if they are long? 
    # For now, let's combine the article content, but keep points structured in text.
    
    content_text = []
    for para in article.get('content', []):
        if para.get('text'):
            content_text.append(para['text'])
        for point in para.get('points', []):
            content_text.append(f"({point['id']}) {point['text']}")
            
    full_text = f"{full_context}\n" + "\n".join(content_text)
    
    training_data.append({
        "id": f"art_{article['id']}",
        "source": "AI Act",
        "type": "article",
        "hierarchy": context.split(' > '),
        "text": full_text
    })

def parse_article(art_div):
    article_data = {
        "type": "article",
        "id": "",
        "title": "",
        "content": []
    }
    
    # Article Number
    art_num_p = art_div.find('p', class_='oj-ti-art')
    if art_num_p:
        article_data['id'] = art_num_p.get_text(strip=True)
        
    # Article Title
    art_tit_div = art_div.find('div', class_='eli-title')
    if art_tit_div:
        article_data['title'] = art_tit_div.get_text(strip=True)
   
    current_paragraph = None
    
    for child in art_div.children:
        if child.name == 'div':
            if 'eli-title' in child.get('class', []):
                continue
            
            # This is likely a numbered paragraph div (e.g. id="001.001")
            para_data = {
                "text": "",
                "points": []
            }
            
            para_text_parts = []
            for p_child in child.children:
                if p_child.name == 'p' and 'oj-normal' in p_child.get('class', []):
                    para_text_parts.append(p_child.get_text(strip=True))
                elif p_child.name == 'table':
                    # Subpoint inside div
                    rows = p_child.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            point_id = cols[0].get_text(strip=True)
                            point_text = cols[1].get_text(strip=True)
                            para_data['points'].append({
                                "id": point_id,
                                "text": point_text
                            })
            
            para_data['text'] = " ".join(para_text_parts)
            article_data['content'].append(para_data)
            current_paragraph = para_data # Update current for potential following tables (unlikely for div)
            
        elif child.name == 'p':
            if 'oj-ti-art' in child.get('class', []):
                continue
            if 'oj-normal' in child.get('class', []):
                # Unnumbered paragraph text
                para_data = {
                    "text": child.get_text(strip=True),
                    "points": []
                }
                article_data['content'].append(para_data)
                current_paragraph = para_data
                
        elif child.name == 'table':
            # Subpoint directly in article (e.g. Article 113)
            # Append to the last paragraph
            if current_paragraph is not None:
                rows = child.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        point_id = cols[0].get_text(strip=True)
                        point_text = cols[1].get_text(strip=True)
                        current_paragraph['points'].append({
                            "id": point_id,
                            "text": point_text
                        })
            else:
                # Table without preceding paragraph. Create a dummy one or handle gracefully.
                # For now, create a new paragraph with empty text.
                para_data = {
                    "text": "",
                    "points": []
                }
                rows = child.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        point_id = cols[0].get_text(strip=True)
                        point_text = cols[1].get_text(strip=True)
                        para_data['points'].append({
                            "id": point_id,
                            "text": point_text
                        })
                article_data['content'].append(para_data)
                current_paragraph = para_data

    # Filter out empty points
    for content in article_data['content']:
        if not content['points']:
            del content['points']

    # Return None if article is effectively empty
    if not article_data['id'] and not article_data['title'] and not article_data['content']:
        return None

    return article_data

if __name__ == "__main__":
    import sys
    import glob
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find all HTML files in the script directory
    html_files = glob.glob(os.path.join(script_dir, "*.html"))
    
    if not html_files:
        print(f"No HTML files found in {script_dir}")
        sys.exit(0)
        
    print(f"Found {len(html_files)} HTML files to process.")
    
    for input_path in html_files:
        filename = os.path.basename(input_path)
        base_name = os.path.splitext(filename)[0]
        
        output_file = f"{base_name}_parsed.json"
        training_output_file = f"{base_name}_training_data.jsonl"
        
        output_path = os.path.join(script_dir, output_file)
        training_output_path = os.path.join(script_dir, training_output_file)

        print(f"\nProcessing: {filename}")
        try:
            parse_html_to_json(input_path, output_path)
            
            # Load the generated JSON to export for training
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            export_for_training(data, training_output_path)
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
