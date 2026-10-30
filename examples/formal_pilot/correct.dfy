method Twice(x: int) returns (r: int)
  ensures r == 2 * x
{
  r := x + x;
}
