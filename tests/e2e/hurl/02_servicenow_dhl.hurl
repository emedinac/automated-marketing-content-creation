POST http://localhost:8000/upload
[MultipartFormData]
sender_id: servicenow
receiver_id: dhl
role: sender
files: file, eval/cases/02_servicenow_dhl/sender.pdf;
HTTP 200
[Asserts]
status == 200

POST http://localhost:8000/upload
[MultipartFormData]
sender_id: servicenow
receiver_id: dhl
role: receiver
files: file, eval/cases/02_servicenow_dhl/receiver.pdf;
HTTP 200
[Asserts]
status == 200

POST http://localhost:8000/generate
Content-Type: application/json
{"sender_id":"servicenow","receiver_id":"dhl","prompt":"Write a concise B2B newsletter article connecting the sender's documented capabilities to the receiver's documented business context.","template_id":"newsletter"}
HTTP 200
[Asserts]
status == 200
jsonpath "$.result.template_id" == "newsletter"
jsonpath "$.result.sections" count > 0
jsonpath "$.result.images" isCollection
jsonpath "$.result.theme" isObject
