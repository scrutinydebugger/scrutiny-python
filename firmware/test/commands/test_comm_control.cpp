#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestCommControl : public ::testing::Test 
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;

   TestCommControl() {}

   virtual void SetUp() 
   {
      scrutiny_handler.init();
   }
};

TEST_F(TestCommControl, TestDiscover) 
{
  
}

