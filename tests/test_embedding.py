import threading
import unittest

from app.embedding import _PriorityCapacity, positive_concurrency


class EmbeddingConfigurationTests(unittest.TestCase):
    def test_embedding_concurrency_must_be_positive_integer(self):
        self.assertEqual(2, positive_concurrency("2"))
        for value in ("0", "-1", "many"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "positive integer"
            ):
                positive_concurrency(value)

    def test_waiting_query_runs_before_queued_add(self):
        capacity = _PriorityCapacity(1)
        order = []
        add_started = threading.Event()
        query_started = threading.Event()

        def run_add():
            add_started.set()
            with capacity.slot(query=False):
                order.append("add")

        def run_query():
            query_started.set()
            with capacity.slot(query=True):
                order.append("query")

        with capacity.slot():
            add_thread = threading.Thread(target=run_add)
            query_thread = threading.Thread(target=run_query)
            add_thread.start()
            self.assertTrue(add_started.wait(1))
            query_thread.start()
            self.assertTrue(query_started.wait(1))
            with capacity._condition:
                self.assertTrue(
                    capacity._condition.wait_for(
                        lambda: capacity._waiting_queries == 1, timeout=1
                    )
                )

        add_thread.join(1)
        query_thread.join(1)
        self.assertFalse(add_thread.is_alive())
        self.assertFalse(query_thread.is_alive())
        self.assertEqual(["query", "add"], order)

    def test_query_burst_eventually_yields_to_queued_add(self):
        capacity = _PriorityCapacity(1, max_query_burst=2)
        order = []
        threads = []

        def run(kind):
            with capacity.slot(query=kind == "query"):
                order.append(kind)

        with capacity.slot():
            threads.append(threading.Thread(target=run, args=("add",)))
            threads[-1].start()
            for _ in range(3):
                threads.append(threading.Thread(target=run, args=("query",)))
                threads[-1].start()
            with capacity._condition:
                self.assertTrue(
                    capacity._condition.wait_for(
                        lambda: capacity._waiting_adds == 1
                        and capacity._waiting_queries == 3,
                        timeout=1,
                    )
                )

        for thread in threads:
            thread.join(1)
            self.assertFalse(thread.is_alive())
        self.assertEqual(["query", "query", "add", "query"], order)


if __name__ == "__main__":
    unittest.main()
