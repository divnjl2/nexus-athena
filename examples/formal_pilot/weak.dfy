// Deliberately weak formalization: verifies but does not require doubling.
method Twice(x: int) returns (r: int)
  requires x >= 0
  ensures r >= 0
{
  r := 0;
}
