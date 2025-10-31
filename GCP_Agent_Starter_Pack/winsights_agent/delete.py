import vertexai
from vertexai.preview import reasoning_engines

# --- Setup ---
PROJECT_ID = "362440398011"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- 1. List all engines ---
print("Listing all reasoning engines...")
engine_list = reasoning_engines.ReasoningEngine.list()
for engine in engine_list:
    print(engine.resource_name)

# --- 2. Delete a specific engine ---
ENGINE_ID_TO_DELETE = "4518082394531561472"  # Paste the ID here
print(f"\nDeleting engine: {ENGINE_ID_TO_DELETE}...")

try:
    # Get a reference to the remote engine
    remote_agent = reasoning_engines.ReasoningEngine(ENGINE_ID_TO_DELETE)
    
    # Call the delete method
    remote_agent.delete()
    
    print(f"Successfully initiated deletion for {ENGINE_ID_TO_DELETE}.")
except Exception as e:
    print(f"Error deleting engine: {e}")