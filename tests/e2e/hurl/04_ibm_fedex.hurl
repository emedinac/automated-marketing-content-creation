POST http://localhost:8000/upload
[MultipartFormData]
sender_id: ibm
receiver_id: fedex
role: sender
files: file, eval/cases/04_ibm_fedex/sender.pdf;
HTTP 200
[Asserts]
status == 200

POST http://localhost:8000/upload
[MultipartFormData]
sender_id: ibm
receiver_id: fedex
role: receiver
files: file, eval/cases/04_ibm_fedex/receiver.pdf;
HTTP 200
[Asserts]
status == 200

POST http://localhost:8000/generate
Content-Type: application/json
{"sender_id":"ibm","receiver_id":"fedex","prompt":"Write a concise B2B newsletter article connecting the sender's documented capabilities to the receiver's documented business context.","template_id":"newsletter"}
HTTP 200
[Asserts]
status == 200
jsonpath "$.result.template_id" == "newsletter"
jsonpath "$.result.sections" count > 0
jsonpath "$.result.images" isCollection
jsonpath "$.result.theme" isObject
