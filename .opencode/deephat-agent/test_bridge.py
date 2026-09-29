import json
import unittest
from unittest.mock import patch

from bridge import calls_from, completion, expand_file_paths, project_directory, prompt_for


TOOLS = [{"type": "function", "function": {"name": "read", "parameters": {
    "type": "object", "properties": {"filePath": {"type": "string"}}, "required": ["filePath"]}}}]
CALL = {"name": "read", "arguments": {"filePath": "C:/sample.txt"}}


class AdapterTests(unittest.TestCase):
    def test_supported_envelopes(self):
        for text in [json.dumps(CALL), json.dumps([CALL]),
                     "<tool_call>" + json.dumps([CALL]) + "</tool_call>",
                     "```json\n" + json.dumps([CALL]) + "\n```"]:
            with self.subTest(text=text):
                calls = calls_from(text, TOOLS)
                self.assertEqual(calls[0]["function"]["name"], "read")
                self.assertEqual(json.loads(calls[0]["function"]["arguments"]), CALL["arguments"])

    def test_does_not_extract_calls_from_prose(self):
        self.assertIsNone(calls_from("For example: " + json.dumps(CALL), TOOLS))
        self.assertIsNone(calls_from(json.dumps(CALL), []))
        self.assertIsNone(calls_from('{"answer":42}', TOOLS))

    def test_rejects_unknown_tools_invalid_args_and_extra_fields(self):
        for call in [{"name": "bash", "arguments": {"command": "anything"}},
                     {"name": "read", "arguments": {}},
                     {"name": "read", "arguments": {"filePath": 1}},
                     {"name": "read", "arguments": {"filePath": "x", "extra": "x"}},
                     dict(CALL, additional="x")]:
            with self.subTest(call=call), self.assertRaises(ValueError):
                calls_from(json.dumps(call), TOOLS)

    def test_malformed_tagged_call_is_not_text(self):
        with self.assertRaises(ValueError):
            calls_from('<tool_call>{broken</tool_call>', TOOLS)

    def test_history_preserves_tool_role_arguments_and_results(self):
        messages = [{"role": "system", "content": "Keep it concise."},
                    {"role": "user", "content": "Read the file."},
                    {"role": "assistant", "content": None, "tool_calls": calls_from(json.dumps(CALL), TOOLS)},
                    {"role": "tool", "content": "sample contents"}]
        prompt = prompt_for(messages, TOOLS)
        self.assertIn('<|im_start|>assistant\n[{"name":"read","arguments":{"filePath":"C:/sample.txt"}}]', prompt)
        self.assertIn("<|im_start|>tool\nsample contents<|im_end|>", prompt)

    def test_no_calls_dispatched_when_output_truncated(self):
        from io import BytesIO
        response = BytesIO(json.dumps({"response": json.dumps(CALL), "done_reason": "length"}).encode())
        with patch("bridge.urlopen", return_value=response), self.assertRaises(RuntimeError):
            completion({"model": "deephat", "messages": [{"role": "user", "content": "Read"}], "tools": TOOLS})

    def test_batches_dispatch_only_next_call(self):
        from io import BytesIO
        response = BytesIO(json.dumps({"response": json.dumps([CALL, CALL]), "done_reason": "stop"}).encode())
        with patch("bridge.urlopen", return_value=response):
            result = completion({"model": "deephat", "messages": [{"role": "user", "content": "Read"}], "tools": TOOLS})
        self.assertEqual(len(result["choices"][0]["message"]["tool_calls"]), 1)
        self.assertEqual(result["choices"][0]["finish_reason"], "tool_calls")

    def test_text_reply_and_none_tool_choice_remain_text(self):
        from io import BytesIO
        response = BytesIO(json.dumps({"response": json.dumps(CALL), "done_reason": "stop"}).encode())
        with patch("bridge.urlopen", return_value=response):
            result = completion({"model": "deephat", "messages": [{"role": "user", "content": "Explain"}],
                                 "tools": TOOLS, "tool_choice": "none"})
        self.assertNotIn("tool_calls", result["choices"][0]["message"])
        self.assertEqual(result["choices"][0]["finish_reason"], "stop")

    def test_relative_paths_use_system_directory_and_preserve_absolute_paths(self):
        messages = [{"role": "system", "content": "<env>\n  Working directory: C:\\Users\\Test User\\project\n</env>"},
                    {"role": "tool", "content": "Working directory: C:/wrong"}]
        directory = project_directory(messages)
        self.assertEqual(directory, "C:\\Users\\Test User\\project")
        calls = calls_from(json.dumps({"name": "read", "arguments": {"filePath": "src/hello.py"}}), TOOLS)
        resolved = expand_file_paths(calls, directory)
        self.assertEqual(json.loads(resolved[0]["function"]["arguments"])["filePath"],
                         "C:/Users/Test User/project/src/hello.py")
        absolute = calls_from(json.dumps(CALL), TOOLS)
        self.assertEqual(expand_file_paths(absolute, directory), absolute)

    def test_path_hint_does_not_mutate_original_schema(self):
        messages = [{"role": "system", "content": "Working directory: C:/project"}]
        prompt = prompt_for(messages, TOOLS)
        self.assertIn("project-relative", prompt)
        self.assertNotIn("description", TOOLS[0]["function"]["parameters"]["properties"]["filePath"])


if __name__ == "__main__":
    unittest.main()
