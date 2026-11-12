from ask import is_safe, run_sql

print("DELETE blocked by is_safe:", not is_safe("DELETE FROM orders"))
print("DROP blocked by is_safe:", not is_safe("DROP TABLE orders"))
print("Two statements blocked:", not is_safe("SELECT 1; DELETE FROM orders"))
print("Normal SELECT allowed:", is_safe("SELECT COUNT(*) FROM orders"))

try:
    run_sql("DELETE FROM orders")
    print("PROBLEM: the delete actually ran")
except Exception as e:
    print("Read-only mode stopped it:", e)