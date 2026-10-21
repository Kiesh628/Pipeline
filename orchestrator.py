from building_modelling import BIM_Node
from building_modelling.topology import Model, Site, Floor, Room, Wall, Window, Roof, Slab
from diagnosis import Issue
from repair.solver import propose_solutions

def diagnose_model() -> list[Issue]:
    master_issue_list = []    
    for node in BIM_Node.registry:
        if hasattr(node, 'verify'):
            node.verify(master_issue_list)
            
    return master_issue_list

def main():
    import os
    from file_extraction import extract_building_graph
    
    # 1. Clear registry to ensure a clean slate
    BIM_Node.clear_registry()
    
    # 2. Extract Real Model
    ifc_file = "Ifc4_SampleHouse.ifc"
    if not os.path.exists(ifc_file):
        print(f"Error: {ifc_file} not found.")
        return
        
    print(f"\n--- EXTRACTING {ifc_file} ---")
    my_model, guid_to_obj = extract_building_graph(ifc_file)
    
    # 3. Diagnose the graph
    print("\n--- RUNNING DIAGNOSTICS ---")
    issues = diagnose_model()
    print(f"Found {len(issues)} issues across the building graph!")
    
    # 4. Feed issues to the Solver Engine
    print("\n--- GENERATING SOLUTIONS ---")
    for issue in issues:
        print(f"\n[ISSUE] {issue}")
        
        solutions = propose_solutions(issue, my_model)
        
        if isinstance(solutions, list):
            for i, sol in enumerate(solutions):
                print(f"  Option {i+1}: {sol.description}")
        else:
            print(f"  FATAL: {solutions.description}")

if __name__ == '__main__':
    main()
