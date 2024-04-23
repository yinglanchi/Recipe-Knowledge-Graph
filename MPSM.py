from gqlalchemy import Memgraph
import openai
import time
import csv
import time

def generate_cypher(recipe_text):
    res = ""
    memgraph = Memgraph("localhost", 7687)
    memgraph.execute('match (n) detach delete n')
    prompt = f'''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{recipe_text}"
             Write cypher statements to create nodes for all ingredients. The correct format is 
             CREATE (:Ingredient open_bracket close_bracket)
             For each ingredient, add all attributes for measure, such as weight and quantity, 
             that are mentioned in the recipe text. 
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
            print("An error occurred:", e)

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
    res += result

    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             Write cypher statements to create nodes for processes.
             For each process, add an attribute called referenceText that specifies the part of the recipe used to create the node.
             Each sentence in the recipe text in the instruction part should contain approximately one process. 
             List all process mentioned in the text, do not simplify. Don't include comments in the response, just 
             the cypher code.
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
    resultList = [item for item in resultList if item != '' and item != ' ' and item != '  ']
    cypher_query = ""
    for cypher_statement in resultList:
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            print("An error occurred:", e)
    res += result

    query = """
            match (n:Process)
            return n.name as name, n.referenceText as referenceText
            """
    result = memgraph.execute_and_fetch(query)
    processes = []
    for record in result:
        processes.append((record['name'], record['referenceText']))
    process_with_reference = ""
    for process, reference in processes:
        process_with_reference += "'" + process + "'" + " given by the reference text " + reference + '\n'
    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             We now have the following processes extracted from the recipe text already: {}. The phrase quoted with 
             single quote is the processes nodes' name already presented in the knowledge graph, and the 
             content following is the reference recipe text of the process. 
             Write cypher statements to update the process nodes with attributes like duration and temperature where 
             applicable by matching by the process nodes' names. 
             Update all attribues mentioned in the graph. Do not simplify.If there's no attributes associated with the process in the 
             recipe text, do not add anything to it. Don't include comments in the response, just the cypher code
             '''.format(recipe_text, process_with_reference)
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
    result = result.replace('cypher', ' ')
    result = result.replace('```', '')
    resultList = result.split('\n')
    resultList = [item for item in resultList if item != '' and item != ' ' and item != '  ']
    i = 0
    cypher_queries = []
    while i < len(resultList):
        try:
            while 'MATCH' not in resultList[i]:
                i += 1
            cypher_query = resultList[i] + ' ' + resultList[i+1] + ' ' + resultList[i+2]
            cypher_queries.append(cypher_query)
            memgraph.execute(cypher_query)
        except Exception as e:
            print("An error occurred:", e)
        cypher_query = ""
        i += 3
    res += result
    tmp = []
    for process, ref in processes:
        tmp.append(process)
        
    # extract all the process nodes in the memgrpah
    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. Conditions in a recipe text refer to specific prerequisites
             and criteria in cooking environment that need to be met during the cooking process. 
             It should contain some criteria like "fry until light brown", etc.
             Here is the recipe text: "{}"
             Write cypher statements to create all condition nodes mentioned in the recipe text.
             Create all condition nodes that are mentioned in the recipe text with the field "name". Do not simplify.
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
    resultList = result.split('\n')
    for cypher_statement in resultList:
        if 'CREATE' not in cypher_statement:
            continue
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            print("An error occurred:", e)

    conditions = []
    query = """
            match (n:Condition)
            return n.name as name
            """
    result = memgraph.execute_and_fetch(query)
    for record in result:
        conditions.append(record['name'])

    cypher_query = []
    for condition in conditions:
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 We now have the following processes extracted from the recipe text already: {}.
                 Which of the process names in the list is associated with the condition "{}"?
                 Write the cypher statement to create an edge labeled by SATISTIES from the associated process nodes
                 (source) to the condition node with name "{}" (target). 
                 Don't include comments and explanation, just the cypher query code.
                 '''.format(recipe_text, ','.join(tmp), condition, condition)
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
        cypher_query.append(result)

    for cypher_statement in cypher_query:
        cypher_statement = cypher_statement.replace('\n', ' ')
        cypher_statement = cypher_statement.replace('```', '')
        cypher_statement = cypher_statement.replace('cypher', '')
        index = cypher_statement.find('MATCH')
        cypher_statement = cypher_statement[index:]
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            print("An error occurred:", e)

    for cypher_statement in cypher_query:
        res += cypher_statement

    #retrieve ingredient nodes and tool nodes
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

    cypher_query = []
    for ingredient in ingredients:
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 We now have the following processes extracted from the recipe text already: {}.
                 Which of the process names in the list USES the ingredient "{}"?
                 Write the cypher statement to create an edge labeled by PREREQ_FOR from the ingredient "{}" to
                 the answer to the above question process nodes.
                 Just list all the cyper statements.
                 Don't include the answer for the first question. Don't include comment in the response.
                 Just the cypher code.
                 '''.format(recipe_text, ','.join(tmp), ingredient, ingredient)
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
        cypher_query.append(result)
        time.sleep(5)
    for cypher_statement in cypher_query:
        cypher_statement = cypher_statement.replace('\n', ' ')
        cypher_statement = cypher_statement.replace('```', '')
        cypher_statement = cypher_statement.replace('cypher', '')
        index = cypher_statement.find('MATCH')
        cypher_statement = cypher_statement[index:]
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            print("An error occurred:", e)
    for cypher_statement in cypher_query:
        res += cypher_statement
        
    cypher_query = []
    for tool in tools:
        prompt = '''
                 A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
                 and semantically rich way to represent the information. I will provide you with a chunk of recipe text
                 that you will built knowledge graph from. 
                 Here is the recipe text: "{}"
                 We now have the following processes extracted from the recipe text already: {}.
                 Which of the process names in the list is associated with the tool "{}"?
                 Write the cypher statement to create an edge labeled by USES from the tool "{}" to
                 the associated process nodes' name. Source should be tool and target should be process.
                 When adding edges, should perform match to search node by name.
                 No need to provide explanantion, just list the cyper statement.
                 '''.format(recipe_text, ','.join(tmp), tool, tool)
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
        cypher_query.append(result)
        time.sleep(5)
    for cypher_statement in cypher_query:
        cypher_statement = cypher_statement.replace('\n', ' ')
        try:
            memgraph.execute(cypher_statement)
        except Exception as e:
            print("An error occurred:", e)
    for cypher_statement in cypher_query:
        res += cypher_statement

    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             We now have the following processes extracted from the recipe text already: {}. These are all process nodes' 
             names in the knowledge graph. 
             Write cypher statements to create FOLLOWED_BY edges between successive processes from the recipe text. 
             All processes listed above should be included. 
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
            print("An error occurred:", e)
    res += result
    # get the final process
    query = '''
            MATCH (n:Process)
            WHERE NOT EXISTS ((n)-[:FOLLOWED_BY]->())
            RETURN n.name as name
            '''
    result = memgraph.execute_and_fetch(query)
    final_processes = []
    for record in result:
        final_processes.append(record['name'])
        
    prompt = '''
             A recipe is a directed acyclic graph (DAG) with heterogeneous nodes and edges provides a structured 
             and semantically rich way to represent the information. I will provide you with a chunk of recipe text
             that you will built knowledge graph from. 
             Here is the recipe text: "{}"
             We now have the final processes extracted from the recipe text already: "{}". These are all process nodes' 
             names in the knowledge graph. 
             Write cypher statements to createthe "FinalProduct" node and connect it to the last action via an edge 
             with the label CREATES. Should perform match to search for the final process node by name.
             The FinalProduct node should have the name the of the recipe.
             '''.format(recipe_text, ','.join(final_processes))
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
    resultList = result.split('\n')
    cypher_query = ""
    for cypher_statement in resultList:
        if 'CREATE' not in cypher_statement:
            continue
        cypher_query += cypher_statement + ' '
    memgraph.execute(cypher_query)

    return res

