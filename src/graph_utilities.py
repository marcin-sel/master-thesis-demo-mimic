from py2neo import Node, Relationship

def check_node_exists(graph, node_type, search_fields):
    where_clause = ' AND '.join([f'n.{key} = ${key}' for key in search_fields.keys()])
    query = f"""
        MATCH (n:{node_type})
        WHERE {where_clause}
        RETURN COUNT(n) > 0 AS exists
    """
    return graph.evaluate(query, **search_fields)

def check_rel_exists(graph, r_type, node1_type, node1_ids, node2_type, node2_ids):
    
    node1_conditions = ",".join([f'{k}: $node1_{k}' for k in node1_ids.keys()])
    node2_conditions = ",".join([f'{k}: $node2_{k}' for k in node2_ids.keys()])
    
    exists = graph.evaluate(
        f"""
        MATCH (a:{node1_type} {{{node1_conditions}}})-[r:{r_type}]->(b:{node2_type} {{{node2_conditions}}})
        RETURN COUNT(r) > 0 AS exists
        """,
        **{f'node1_{k}': v for k, v in node1_ids.items()},
        **{f'node2_{k}': v for k, v in node2_ids.items()}
    )

    return exists

def create_nodes(graph, df, node_type, id_fields, name_field, exclude_attrs):
    tx = graph.begin()
    cached_nodes = {}
    for _, r in df.iterrows():
        ids = {k: v for k, v in dict(r).items() if k in id_fields}

        if not check_node_exists(graph, node_type, ids):
            attrs = {k: v for k, v in dict(r).items() if k not in exclude_attrs}
            attrs.update(ids)
            n = Node(node_type, name=r[name_field], **attrs)
            tx.create(n)
            
            cached_nodes[(ids.get(id_field) for id_field in id_fields)] = n

    graph.commit(tx)
    return cached_nodes
 

def create_relationships(
    graph,
    df,
    node1_type,
    node2_type,
    node1_id_fields,
    node2_id_fields,
    r_type,
    exclude_fields=None,
):

    if exclude_fields is None:
        exclude_fields = []

    tx = graph.begin()

    for _, r in df.iterrows():
        row_dict = dict(r)

        node1_ids = {k: v for k, v in row_dict.items() if k in node1_id_fields}
        node2_ids = {k: v for k, v in row_dict.items() if k in node2_id_fields}

        node1 = graph.nodes.match(node1_type, **node1_ids).first()
        node2 = graph.nodes.match(node2_type, **node2_ids).first()

        exists = check_rel_exists(
            graph=graph,
            r_type=r_type,
            node1_type=node1_type,
            node2_type=node2_type,
            node1_ids=node1_ids,
            node2_ids=node2_ids,
        )

        if node1 and node2 and not exists:
            attrs = {k: v for k, v in row_dict.items() if k not in exclude_fields}
            rel = Relationship(node1, r_type, node2, **attrs)
            tx.create(rel)

    graph.commit(tx)
