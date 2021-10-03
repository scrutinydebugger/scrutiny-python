#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestMemoryControl : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;
   scrutiny::config config

   TestMemoryControl() {}

   virtual void SetUp() 
   {
      scrutiny::Config config;
      scrutiny_handler.init(&config);
      scrutiny_handler.enable_comm();
   }
};

TEST_F(TestMemoryControl, TestReadSingleAddress) 
{

}

