from Text_To_SQL_Langraph import app

graph = app.get_graph(xray=True)
png_bytes = graph.draw_mermaid_png()

with open("langgraph_diagram.png", "wb") as f:
    f.write(png_bytes)
