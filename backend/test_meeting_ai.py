
from app.meeting_ai import analyze_transcript

sample_transcript = """
Customer: We are interested in the premium plan.
Salesperson: I will send the revised proposal by Friday.
Customer: Great. Our finance team will review it next week.
"""

result = analyze_transcript(sample_transcript)

print("\n--- DEALPILOT AI MEETING ANALYSIS ---\n")
print(result)
