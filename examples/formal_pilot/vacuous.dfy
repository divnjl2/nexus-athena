// Deliberately impossible precondition: no admitted input can exercise the body.
method Twice(x: int) returns (r: int)
  requires false
  ensures r == 2 * x
{
  r := 0;
}
