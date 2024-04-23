from gqlalchemy import Memgraph
import openai
import time
import csv
import time
import spacy

memgraph = Memgraph("localhost", 7687)

def split_into_chunks(text, k):
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]
    chunks = [sentences[i:i + k] for i in range(0, len(sentences), k)]
    return chunks

def add_processes(result):
    resultList = result.split('\n')
    resultList = [item for item in resultList if item != '' and item != ' ' and item != '  ']
    cypher_query = ""
    for cypher_statement in resultList:
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                memgraph.execute(response['choices'][0]['message']['content'])
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)

def add_followed_by(result):
    result = result.replace('cypher', ' ')
    result = result.replace('```', '')
    resultList = result.split('\n\n')
    for cypher_statement in resultList:
        cypher = ""
        tmp = cypher_statement.split('\n')
        for query in tmp:
            if '//' in tmp:
                continue
            cypher += query + ' '
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion. If the error message is "MATCH can't be put after RETURN clause or after an update.", add \n\n after each merge before the next match statement comes in.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                tmp = response['choices'][0]['message']['content']
                tmp = tmp.replace('cypher', '')
                tmp = tmp.replace('```', '')
                tmpList = tmp.split('\n\n')
                for query in tmpList:
                    memgraph.execute(query)
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)

def generate_cypher(recipe_text):
    memgraph.execute('match (n) detach delete n')
    runtime = []
    res = ""
    start_time = time.time()
    prompt = f'''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{recipe_text}"
             Write cypher statements to create nodes for all ingredients. The correct format is 
             CREATE (:Ingredient open_bracket close_bracket)
             For each ingredient, add all attributes for measure, such as weight and quantity, that are mentioned in the 
             recipe text. 
             No comments in the response.
             '''
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
        )
    result = response['choices'][0]['message']['content']
    res += result
    resultList = result.split('\n')
    for cypher_statement in resultList:
        if 'CREATE' not in cypher_statement:
            continue
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to make it correct. 
                     Output only the correct cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                memgraph.execute(response['choices'][0]['message']['content'])
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)
    end_time = time.time()
    runtime.append(end_time - start_time)
    
    start_time = time.time()
    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             Write cypher statements to create nodes for all tools mentioned in the recipe text. 
             No comments in the response.
             '''.format(recipe_text)
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
        )
    result = response['choices'][0]['message']['content']
    resultList = result.split('\n')
    for cypher_statement in resultList:
        if 'CREATE' not in cypher_statement:
            continue
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            print("An error occurred:", e)
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                memgraph.execute(response['choices'][0]['message']['content'])
            except Exception as e:
                print(e)
    res += result
    end_time = time.time()
    runtime.append(end_time - start_time)
    
    start_time = time.time()
    index = recipe_text.lower().find("instructions")
    instructions=recipe_text[index+len("instructions"):].strip()
    chunks = split_into_chunks(instructions, 5)
    for chunk in chunks:
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 Write cypher statements to create nodes for processes.
                 For each process, add an attribute called referenceText that specifies the part of the recipe used to create the
                 node.
                 Each sentence in the recipe text in the instruction part should contain approximately one process. 
                 List all process mentioned in the text, do not simplify. Don't include comments in the response, just 
                 the cypher code. Create the referenceText and name field together within the create statement. Do not create the
                 referenceText field by using set. 
                 '''.format(' '.join(chunk))
        response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
        result = response['choices'][0]['message']['content']
        res += result
        add_processes(result)
    end_time = time.time()
    runtime.append(end_time - start_time)
    
    start_time = time.time()
    query = """
            match (n:Process)
            return n.name as name, n.referenceText as referenceText
            """
    result = memgraph.execute_and_fetch(query)
    processes = []
    for record in result:
        processes.append((record['name'], record['referenceText']))

    result = ""
    process_with_reference = ""
    for process, reference in processes:
        if process is None:
            continue
        if reference is not None:
            process_with_reference += "(" + process + ", " + reference + '),'
        else:
            process_with_reference += "(" + process + ", " + " " + '),'
    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             We now have the following processes extracted from the recipe text already: {}. The first element 
             is the process node's name attribute, and the second element is the process node's referenceText attribute. 
             Write cypher statements to update the process nodes with attributes like duration and temperature where 
             applicable.
             The format of the cypher queries should look like:

             Match (p:Process)
             Where (p.name = ... or p.referenceText = ...)
             SET p.... = ... 

             Update all attribues mentioned in the graph. Do not simplify.If there's no attributes associated with the process in 
             the recipe text, do not add anything to it. Please perform match perform set. Don't do set directly, because this 
             will cause unbound variable cypher errors.Don't include comments in the response, just the cypher code. Don't forget 
             to add a \n\n after each set and before the next match.
             '''.format(recipe_text, process_with_reference)
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
        )
    result += response['choices'][0]['message']['content']
    result = result.replace('cypher', ' ')
    result = result.replace('```', '')
    resultList = result.split('\n\n')
    for cypher_statement in resultList:
        cypher_statement = cypher_statement.replace('\n', ' ')
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion. If the error message is "MATCH can't be put after RETURN clause or after an update.", add \n\n after each merge before the next match statement comes in.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                tmp = response['choices'][0]['message']['content']
                tmp = tmp.replace('cypher', '')
                tmp = tmp.replace('```', '')
                tmpList = tmp.split('\n\n')
                for query in tmpList:
                    memgraph.execute(query)
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)
    res += result
    end_time = time.time()
    runtime.append(end_time - start_time)

    start_time = time.time()
    tmp = []
    for process, ref in processes:
        if process is None:
            continue
        tmp.append(process)

    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. Conditions in a recipe text refer to specific prerequisites
             and criteria in cooking environment that need to be met during the cooking process. 
             It should contain some criteria like "fry until light brown", etc.
             Here is the recipe text: "{}"
             Write cypher statements to create all condition nodes mentioned in the recipe text.
             Create all condition nodes that are mentioned in the recipe text with the field "name". Do not simplify. Don't
             forget to add a \n\n after each create before the next create comes in.
             '''.format(recipe_text, ','.join(tmp))
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
        )
    result = response['choices'][0]['message']['content']
    res += result

    resultList = result.split('\n\n')
    for cypher_statement in resultList:
        if 'CREATE' not in cypher_statement:
            continue
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                memgraph.execute(response['choices'][0]['message']['content'])
            except Exception as e:
                print(e)
    end_time = time.time()
    runtime.append(end_time - start_time)

    start_time = time.time()
    conditions = []
    query = """
            match (n:Condition)
            return n.name as name
            """
    result = memgraph.execute_and_fetch(query)
    for record in result:
        conditions.append(record['name'])

    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             We now have the following processes extracted from the recipe text already: {}.
             We now have the following conditions extracted from the recipe text already: {}.
             Write the cypher statement to create edges labeled by SATISTIES from process nodes to the associated
             condition nodes. Both should come from the provided list above, match the exact name given.
             Do not connect process to process or condition to condition, only process to condition.
             The format of the cypher queries should look like:

             Match (p:Process), (c:Condition)
             Where p.name = ... and c.name = ...
             Merge (p)-[r:SATISFIES]->(c) 

             Do not select process names in the condition list,and do not select condition names in the process list.
             Do not select process names outside of the process list, and do not select condition names outside of the 
             condition list. Don't forget to add a \n\n after each set and before the next match.
             Match the name exactly as given, do not modify the names such as adding ing to the verbs, capitalize
             certain letters, left of certain portions of the name, etc.
             Don't include comments and explanation, just the cypher query code.
             '''.format(instructions, ','.join(tmp), ','.join(conditions))
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
        ]
    )
    result = response['choices'][0]['message']['content']
    result = result.replace('cypher', ' ')
    result = result.replace('```', '')
    resultList = result.split(';')
    for cypher_statement in resultList:
        cypher_statement = cypher_statement.replace('\n', ' ')
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                tmp = response['choices'][0]['message']['content']
                tmp = tmp.replace('cypher', '')
                tmp = tmp.replace('```', '')
                tmpList = tmp.split('\n\n')
                for query in tmpList:
                    memgraph.execute(query)
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)
    res += result
    end_time = time.time()
    runtime.append(end_time - start_time)

    start_time = time.time()
    ingredients = []
    tools = []
    query = '''
            Match (n:Ingredient)
            return n.name as name
            '''
    result = memgraph.execute_and_fetch(query)
    for record in result:
        ingredients.append(record['name'])

    query = '''
            Match (n:Tool)
            return n.name as name
            '''
    result = memgraph.execute_and_fetch(query)
    for record in result:
        tools.append(record['name'])

    result = ""
    for i in range(len(processes)//50+1):
        process_group = processes[i*50:min(i*50+50, len(processes))]
        process_with_reference_group = ""
        for process, reference in process_group:
            if process is None:
                continue
            if reference is not None:
                process_with_reference_group += "(" + process + ", " + reference + '),'
            else:
                process_with_reference_group += "(" + process + ", " + " " + '),'
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 We now have the following processes extracted from the recipe text already: {}. 
                 we now have the following ingredients extracted from the recipe text already: {}.
                 Write the cypher statement to create an edge labeled by PREREQ_FOR from the ingredient to processes
                 that uses the ingredient. 
                 The format of the cypher queries should look like:

                 Match (p:Process), (i:Ingredient)
                 Where (p.name = ... or p.referenceText = ...) and i.name = ...
                 Merge (i)-[r:PREREQ_FOR]->(p)


                 Do not select process names in the ingredient list,and do not select ingredient names in the process list.
                 Do not select process names outside of the process list, and do not select ingredient names outside of the 
                 ingredient list. Don't forget to add a \n\n at the end of each merge before the next match.
                 Match the name exactly as given, do not modify the names such as adding ing to the verbs, capitalize
                 certain letters, left of certain portions of the name, left of punctuations, etc.
                 Don't include comments and explanation, just the cypher query code.
                 '''.format(instructions, process_with_reference_group, ','.join(ingredients))
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
        )
        result += response['choices'][0]['message']['content']

    result = result.replace('cypher', ' ')
    result = result.replace('```', '')
    resultList = result.split('\n\n')
    for cypher_statement in resultList:
        cypher_statement = cypher_statement.replace('\n', ' ')
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                tmp = response['choices'][0]['message']['content']
                tmp = tmp.replace('cypher', '')
                tmp = tmp.replace('```', '')
                tmpList = tmp.split('\n\n')
                for query in tmpList:
                    memgraph.execute(query)
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)
    res += result
    end_time = time.time()
    runtime.append(end_time - start_time)
    
    start_time = time.time()
    result = ""
    for i in range(len(processes)//50+1):
        process_group = processes[i*50:min(i*50+50, len(processes))]
        process_with_reference_group = ""
        for process, reference in process_group:
            if process is None:
                continue
            if reference is not None:
                process_with_reference_group += "(" + process + ", " + reference + '),'
            else:
                process_with_reference_group += "(" + process + ", " + " " + '),'
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 We now have the following processes extracted from the recipe text already: {}. 
                 we now have the following tools extracted from the recipe text already: {}.
                 Write the cypher statement to create an edge labeled by USES from the process to tools
                 that it needs to use.
                 The format of the cypher queries should look like:

                 Match (p:Process), (t:Tool)
                 Where (p.name = ... or p.referenceText = ...) and t.name = ...
                 MERGE (t)-[r:USES]->(p)


                 Do not select process names in the tool list,and do not select tool names in the process list.
                 Do not select process names outside of the process list, and do not select tool names outside of the 
                 tool list. Don't forget to add a \n\n at the end of each merge before the next match.
                 Match the name exactly as given, do not modify the names such as adding ing to the verbs, capitalize
                 certain letters, left of certain portions of the name, left of punctuations, etc.
                 Don't include comments and explanation, just the cypher query code.
                 '''.format(instructions, process_with_reference_group, ','.join(tools))
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ]
        )
        result += response['choices'][0]['message']['content']
        
    result = result.replace('cypher', ' ')
    result = result.replace('```', '')
    resultList = result.split('\n\n')
    for cypher_statement in resultList:
        cypher_statement = cypher_statement.replace('\n', ' ')
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                tmp = response['choices'][0]['message']['content']
                tmp = tmp.replace('cypher', '')
                tmp = tmp.replace('```', '')
                tmpList = tmp.split('\n\n')
                for query in tmpList:
                    memgraph.execute(query)
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)
    res += result
    end_time = time.time()
    runtime.append(end_time - start_time)

    start_time = time.time()
    for chunk in chunks:
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 We now have the following processes extracted from the recipe text already: {}. 
                 These are all process nodes'names in the knowledge graph. 
                 Write cypher statements to create FOLLOWED_BY edges between processes from the recipe text. 
                 Connect the processes one by one, do not connect a chunk of processes to another chunk of processes.
                 Do not have to use all processes in the given list. Just connect the sequential processes covered.
                 The format of the cypher queries should look like:

                 Match (p1:Process), (p2:Process)
                 Where p1.name = ... and p2.name = ...
                 MERGE (p1)-[r:FOLLOWED_BY]->(p2)

                 All processes listed above should be included.
                 '''.format(' '.join(chunk), process_with_reference)
        response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ],
                max_tokens=1000
            )
        result = response['choices'][0]['message']['content']
        res += result
        add_followed_by(result)
    end_time = time.time()
    runtime.append(end_time - start_time)

    start_time = time.time()
    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             Write cypher statements to create the "FinalProduct" node. 
             The FinalProduct node should have the name the of the recipe.
             '''.format(instructions, process_with_reference)
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ],
            max_tokens=1000
        )
    result = response['choices'][0]['message']['content']

    resultList = result.split('\n')
    cypher_query = ""
    for cypher_statement in resultList:
        if 'CREATE' not in cypher_statement:
            continue
        cypher_query += cypher_statement + ' '
    memgraph.execute(cypher_query)
    res += result
    end_time = time.time()
    runtime.append(end_time - start_time)

    start_time = time.time()
    finalProduct = []
    query = """
            match (n:FinalProduct)
            return n.name as name
            """
    result = memgraph.execute_and_fetch(query)
    for record in result:
        finalProduct.append(record['name'])

    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             We have extracted all processes from the recipe text already: "{}". These are all process nodes' 
             names in the knowledge graph. 
             We have the FinalProduct node with name {}
             Write cypher statements to connect the FinalProduct node to the last process in the recipe
             text in the given process list via an edge with the label CREATES. 
             Do not add extra nodes. 
             The format of the cypher queries should look like:

             MATCH (p:Process), (f:FinalProduct)
             WHERE (p.name = ... or p.referenceText = ...) and f.name = ...
             MERGE (p)-[:CREATES]->(f);
             \n\n

             The FinalProduct node should have the name the of the recipe. Don't forget to add a ; after each merge before
             the next match comes in to avoid the mismatched input errors.
             Follow the format above, do not create the CREATES edges by MATCH (n:Process)-[:CREATES]->(f:FinalProduct) without 
             having the merge.
             '''.format(instructions, process_with_reference, finalProduct[0])
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ],
            max_tokens=1000
        )
    result = response['choices'][0]['message']['content']
    res += result
    resultList = result.split(';')
    cypher_query = ""
    for cypher_statement in resultList:
        cypher_statement = cypher_statement.replace('\n', ' ')
        try:
            memgraph.execute(cypher_query)
        except Exception as e:
            prompt = '''
                     The cypher statement {} leads to error {}. Modify the statement to debug. Output only the correct
                     cypher statement, no explanantion.
                     '''.format(cypher_statement, e)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                ]
            )
            try:
                tmp = response['choices'][0]['message']['content']
                tmp = tmp.replace('cypher', '')
                tmp = tmp.replace('```', '')
                tmpList = tmp.split('\n\n')
                for query in tmpList:
                    memgraph.execute(query)
            except Exception as e:
                print(response['choices'][0]['message']['content'])
                print(e)
    end_time = time.time()
    runtime.append(end_time - start_time)
    return res, runtime



